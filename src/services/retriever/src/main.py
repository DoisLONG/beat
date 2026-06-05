# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os, sys
import time
from typing import List, Optional, Callable
import asyncio
import json
import re
import glob

from pymilvus import MilvusException
from pymilvus import connections, utility, Collection

from fastapi import HTTPException, Request
from contextlib import asynccontextmanager

from opea_cores import (
    EmbedDoc,
    SearchedDoc,
    ServiceType,
    MetadataTextDoc,
)

from .config import (
    logger,
    CONNECTION_ARGS,
    embedding_function,
    KBS_INFO_DIR,
)
from .patching import MyMilvus

from docarray import BaseDoc

# retriever input text pattern
re_userinput = re.compile('user: (.*)\nassistant:')

# global var for all kb infos
all_kb_infos = {}
# for "kb-name" -> kb-id lookup
kbs_rev_maps = {}

# actually we need not this lock if save it to app.state, but for current core module design, we must
kb_infos_lock = asyncio.Lock()

async def get_all_kbinfos(force: bool = False):
    global all_kb_infos

    if all_kb_infos: # should be atomic op
        if not force: return

    # to record all questions files for later cleanup
    qfile_list = []

    new_infos = {}
    try:
        connections.connect("default", **CONNECTION_ARGS)
        collections = utility.list_collections()
        
        logger.info(f"[milvus raw list] {collections}")

        for kb in collections:
            logger.info(f"[query kb] {kb}")

            collection = Collection(kb)
            collection.load()

            logger.info(f"[kb schema] {collection.schema}")
            logger.info(f"[kb description] {collection.description}")

            # TODO get filename list from partitions metainfo

            try:
                if any(field.name == 'kb_id' for field in collection.schema.fields):
                    docs = collection.query(
                        expr="pk != 0",
                        output_fields=["kb_name", "kb_id", "docnm_kwd"],
                        timeout=10,
                    )
                else: # old format db
                    logger.info(f"[old format db] {kb}")
                    docs = collection.query(
                        expr="pk != 0",
                        output_fields=["filename"],
                        timeout=10,
                    )

                logger.debug(f"[query res count] {len(docs)}")
                if docs:
                    logger.debug(f"[query 1st res] {docs[0]}")

                collection.release()
            except MilvusException as e:
                logger.error(f"[query failed, ignore] {e}")
                continue

            this_kbinfo = {}
            for doc in docs:
                try:
                    if 'kb_name' in doc:
                        if not this_kbinfo:
                            this_kbinfo['name'] = doc['kb_name']
                            this_kbinfo['uuid'] = doc['kb_id']
                            this_kbinfo['files'] = set([doc['docnm_kwd']])
                        else:
                            this_kbinfo['files'].add(doc['docnm_kwd'])
                    else:
                        if not this_kbinfo:
                            this_kbinfo['name'] = kb
                            this_kbinfo['uuid'] = ""
                            this_kbinfo['files'] = set([doc['filename']])
                        else:
                            this_kbinfo['files'].add(doc['filename'])

                except KeyError:
                    logger.error(f"[invalid collection, ignore] {kb}")
                    this_kbinfo = None
                    break

            if this_kbinfo:
                unique_files = list(this_kbinfo['files'])
                this_kbinfo['files'] = unique_files
                new_infos[kb] = this_kbinfo

                # load questions from file
                qlist_fp = os.path.join(KBS_INFO_DIR, f'{kb}_questions.json')
                qfile_list.append(qlist_fp)
                logger.info(f"[trying to load questions from file] {qlist_fp}")
                if os.path.exists(qlist_fp):
                    with open(qlist_fp, 'r') as f:
                        try:
                            this_kbinfo['questions'] = json.load(f)['questions']
                        except KeyError:
                            this_kbinfo['questions'] = []
                            logger.error(f"[invalid questions file, ignore] {qlist_fp}")
                else:
                    with open(qlist_fp, 'w') as f:
                        this_kbinfo['questions'] = []
                        json.dump({'kb_name': this_kbinfo['name'], 'questions': this_kbinfo['questions']}, f, indent=4)
                        logger.info(f"[created new questions file] {qlist_fp}")

        # collections loop end
        logger.debug(f"[get kbs] {new_infos}")

        # clean up deprecated files for dropped kbs
        for qfile in glob.glob(os.path.join(KBS_INFO_DIR, '*_questions.json')):
            if qfile not in qfile_list:
                # archive it instead of removing
                os.makedirs(os.path.join(KBS_INFO_DIR, 'archive'), exist_ok=True)
                os.rename(qfile, os.path.join(KBS_INFO_DIR, 'archive', os.path.basename(qfile)))
                logger.info(f"[archive deprecated questions file] {os.path.basename(qfile)} -> archive")

    except MilvusException as e:
        logger.error(f"Error retrieving collections: {e}")

    async with kb_infos_lock:
        all_kb_infos.clear()
        all_kb_infos.update(new_infos)

        # clear and rebuild the reverse map
        kbs_rev_maps.clear()
        for kb_id in all_kb_infos:
            kbs_rev_maps[all_kb_infos[kb_id]['name']] = kb_id

# decorator for all endpoints that need to get all kb infos
def prepare_kbinfos(func):
    async def wrapper(*args, **kwargs):
        await get_all_kbinfos()
        return await func(*args, **kwargs)
    return wrapper

def try_to_load_json(s):
    """
    Attempt to parse a string as JSON.
    :param s: The string to check.
    :return: The parsed JSON object if valid, otherwise None.
    """
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return None

def parse_input_text(input_text: str):
    """
    parse input text to extract the question part
    :param input_text: The input text to parse.
    :return: The question part of the input text.
    """

    # input text will be json
    if parsed_json := try_to_load_json(input_text):
        messages = parsed_json
    # input text will be: 'text': 'user: what is deep learning\nassistant: i am fine😊\n'
    elif (match := re_userinput.match(input_text)) and match.group(1):
        messages = [{"role": "user", "content": match.group(1).strip()}]
    else:
        messages = [{"role": "user", "content": input_text.strip()}]
    
    last_content = messages[-1].get("content", "")
    return last_content

async def _retrieve(input: EmbedDoc) -> SearchedDoc:
    kb_name = input.collection_name

    # detect old or new vector data fmt
    kb_fmt_new = True
    async with kb_infos_lock:
        try:
            if all_kb_infos and all_kb_infos[kb_name]['uuid'] == "":
                # old format db
                kb_fmt_new = False
        except KeyError:
            pass

    input_question_only = parse_input_text(input.text)

    log_info = {
        'text': input.text,
        'question_only': input_question_only,
        'search_type': input.search_type,
        'k': input.k,
        'distance_threshold': input.distance_threshold,
        'fetch_k': input.fetch_k,
        'lambda_mult': input.lambda_mult,
        'score_threshold': input.score_threshold,
        'constraints': input.constraints,
        'collection_name': kb_name
    }
    logger.debug(f"Input parameters: {log_info}")

    if not kb_name: # None or ''
        # 404
        raise HTTPException(status_code=404, detail="Collection not found")

    if not all_kb_infos:
        raise HTTPException(status_code=404, detail="Collections not found")

    if kb_fmt_new:
        vector_field = "q_1024_vec"
        text_field = "content_with_weight"
        score_threshold = input.score_threshold
        # TODO threshhold_score to be tuned for old and new data fmt
    else:
        vector_field = "vector"
        text_field = "text"
        score_threshold = input.score_threshold

    # old milvus db: collection_name is also the showing name
    # new milvus db: collection_name is kb-id, and showing name is kb-name
    try:
        kb_realname = kbs_rev_maps[kb_name]
    except:
        kb_realname = kb_name

    vector_db = MyMilvus(
        embedding_function,
        connection_args = CONNECTION_ARGS,
        collection_name = kb_realname,

        vector_field = vector_field,
        text_field = text_field,
        enable_dynamic_field=True,

        index_params = {"index_type": "FLAT", "metric_type": "IP", "params": {}}
    )

    search_res = None
    if input.search_type == "similarity":
        search_res = await vector_db.asimilarity_search_by_vector(embedding=input.embedding, k=input.k)
    elif input.search_type == "similarity_distance_threshold":
        if input.distance_threshold is None:
            raise ValueError("distance_threshold must be provided for " + "similarity_distance_threshold retriever")
        search_res = await vector_db.asimilarity_search_by_vector(
            embedding=input.embedding, k=input.k, distance_threshold=input.distance_threshold
        )
    elif input.search_type == "similarity_score_threshold":
        docs_and_similarities = await vector_db.asimilarity_search_with_relevance_scores(
            query=input_question_only, k=input.k, score_threshold=score_threshold,
        )

        for doc, similarity in docs_and_similarities:
            logger.debug(f"Search result with similarity score: content={doc.page_content}, metadata={doc.metadata}, similarity={similarity}")

        search_res_score = [{"doc": doc, "similarity": similarity} for doc, similarity in docs_and_similarities]
    elif input.search_type == "mmr":
        search_res = await vector_db.amax_marginal_relevance_search(
            query=input_question_only, k=input.k, fetch_k=input.fetch_k, lambda_mult=input.lambda_mult
        )
    else:
        logger.error("Invalid search type")
        raise HTTPException(status_code=400, detail="Invalid search type")

    if search_res:
        search_res_score = [{"doc": doc, "similarity": 0} for doc in search_res]

    searched_docs = []
    for r in search_res_score:
        if not kb_fmt_new:
            # add field "filepath" to metadata
            r["doc"].metadata["filepath"] = kb_name + "/" + r["doc"].metadata["filename"]
            searched_docs.append(MetadataTextDoc(text=r["doc"].page_content, metadata=r["doc"].metadata))
        else:
            metadata = r["doc"].metadata
            uuid = metadata['kb_id']
            for i in range(len(metadata["position_int"])):
                newmeta = {
                    "filename": metadata["docnm_kwd"],
                    "filepath": uuid + "/" + metadata["docnm_kwd"],
                    "score": r["similarity"],
                    "page": {
                        "page_num": metadata["position_int"][i][0],
                        # currently only support pdf
                        "width": metadata.get("width", 0),
                        "height": metadata.get("height", 0),
                    },
                    "rect": {
                        "x1": metadata["position_int"][i][1],
                        "x2": metadata["position_int"][i][2],
                        "y1": metadata["position_int"][i][3],
                        "y2": metadata["position_int"][i][4],
                    },
                }
                searched_docs.append(MetadataTextDoc(text=r["doc"].page_content, metadata=newmeta))

    result = SearchedDoc(retrieved_docs=searched_docs, initial_query=input.text)

    logger.debug(f"Search result - Initial Query: {result.initial_query}")
    logger.debug(f"Search result - Retrieved Docs: {result.retrieved_docs}")
    return result

@prepare_kbinfos
async def _list_kbs() -> dict:
    async with kb_infos_lock:
        # {"kb-name": "uuid"} to adapt with UI
        return {all_kb_infos[kb]['name']: all_kb_infos[kb]['uuid'] for kb in all_kb_infos.keys()}

@prepare_kbinfos
async def _get_kbinfo(kb_id: str) -> dict:
    async with kb_infos_lock:
        if kb_id in all_kb_infos:
            return all_kb_infos[kb_id]
        else:
            return {}

@prepare_kbinfos
async def _get_kb_files(kb_id: str) -> list[dict]:
    async with kb_infos_lock:
        if kb_id in all_kb_infos:
            return [{
                      'name': file,
                      'id': all_kb_infos[kb_id]['uuid'] + '/' + file,
                      'type': 'File',
                      'parent': '',
                      } for file in all_kb_infos[kb_id]['files']]
        else:
            return []

@prepare_kbinfos
async def _get_kb_questions(kb_id: str) -> list[str]:
    async with kb_infos_lock:
        if kb_id in all_kb_infos:
            return all_kb_infos[kb_id]['questions']
        else:
            return []

class DifyRetrievalSetting(BaseDoc):
    top_k: int = 4
    score_threshold: float = 0.5
class DifyRetrievalRequest(BaseDoc):
    query: str
    knowledge_id: str
    retrieval_setting: DifyRetrievalSetting

async def _dify_retrieval(input: DifyRetrievalRequest):

    logger.debug(f"Dify-API inputs: {input.model_dump() if hasattr(input, 'dict') else input}")

    embed_doc = EmbedDoc(
        collection_name=input.knowledge_id,
        text=input.query,
        search_type="similarity_score_threshold",
        k=input.retrieval_setting.top_k,
        score_threshold=input.retrieval_setting.score_threshold,
        embedding=[1.0, 1.0], # Fake value,only because EmbedDoc requires
        # distance_threshold=None,
        # fetch_k=None,
        # lambda_mult=None,
        # constraints=None,
    )
    ekba_result = await _retrieve(embed_doc)
    logger.debug(f"Dify-API EKBA retrieved: {ekba_result.model_dump() if hasattr(ekba_result, 'dict') else ekba_result}")
    dify_results = {
        "records": [
            {
                "metadata": {
                    "path": f"s3://{doc.metadata.get('filepath', '')}",
                    "description": doc.metadata.get('description', 'No description available')
                },
                "score": doc.metadata.get('score', 0),
                "title": doc.metadata.get('filename', 'Untitled'),
                "content": doc.text
            }
            for doc in ekba_result.retrieved_docs
        ]
    }
    logger.debug(f"Dify-API return data to Dify: {dify_results}")
    return dify_results


if __name__ == "__main__":
    # command line running 
    # is the production entry point with opea cores wrappers
    from opea_cores import opea_microservices, register_microservice, register_statistics, statistics_dict

    # main entry of this service, with full registration info
    @register_microservice(
        name="opea_service@retriever_new", service_type=ServiceType.RETRIEVER,
        host="0.0.0.0", port=7001,
        methods=["POST"], endpoint="/v1/retrieval",
    )
    @register_statistics(names=["opea_service@retriever_new"])
    async def opeasvc_retrieve(input: EmbedDoc) -> SearchedDoc:
        # TODO, if it's necessary, add it back here
        # starting_time = time.time()
        # ?? why use it? statistics_dict["opea_service@retriever_new"].append_latency(time.time() - starting_time, None)
        return await _retrieve(input)

    @register_microservice(name="opea_service@retriever_new",
        methods=["POST"], endpoint="/v1/dify/retrieval",
    )
    async def opeasvc_dify_retrieval(request: DifyRetrievalRequest):
        return await _dify_retrieval(request)

    ## Belows is the KB Info API

    @register_microservice(name="opea_service@retriever_new",
        methods=["POST"], endpoint="/v1/kbs",
    )
    async def opeasvc_refresh_kbs():
        await get_all_kbinfos(force=True)
        return {"message": "KBs refreshed"}

    @register_microservice(name="opea_service@retriever_new",
        methods=["GET"], endpoint="/v1/kbs",
    )
    async def opeasvc_list_kbs() -> dict:
        return await _list_kbs()

    @register_microservice(name="opea_service@retriever_new",
        methods=["GET"], endpoint="/v1/kbs/{kb_id}",
    )
    async def opeasvc_get_kbinfo(kb_id: str) -> dict:
        return await _get_kbinfo(kb_id)

    @register_microservice(name="opea_service@retriever_new",
        methods=["GET"], endpoint="/v1/kbs/files/{kb_id}",
    )
    async def opeasvc_get_kb_files(kb_id: str) -> list[dict]:
        return await _get_kb_files(kb_id)

    @register_microservice(name="opea_service@retriever_new",
        methods=["GET"], endpoint="/v1/kbs/questions/{kb_id}",
    )
    async def opeasvc_get_kb_questions(kb_id: str) -> list[str]:
        return await _get_kb_questions(kb_id)

    # TODO, failed to make it actually work, need to modify opea_cores later
    @opea_microservices["opea_service@retriever_new"].app.on_event("startup")
    async def startup_event():
        await get_all_kbinfos()

    opea_microservices["opea_service@retriever_new"].start()

else:
    # standard fastapi app development mode with auto reload
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    @asynccontextmanager
    async def lifespan(app):
        await get_all_kbinfos()
        yield

    app = FastAPI(lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/v1/health_check")
    async def _health_check():
        return {"Service Title": "Retriever New"}

    @app.post("/v1/retrieval")
    async def api_retrieve(input: EmbedDoc) -> SearchedDoc:
        return await _retrieve(input)

    @app.post("/v1/dify/retrieval")
    async def api_dify_retrieve(request: DifyRetrievalRequest):
        return await _dify_retrieval(request)

    ## Belows is the KB Info API

    @app.post("/v1/kbs")
    async def api_refresh_kbs():
        await get_all_kbinfos(force=True)
        return {"message": "KBs refreshed"}

    @app.get("/v1/kbs")
    async def api_list_kbs() -> dict:
        return await _list_kbs()

    @app.get("/v1/kbs/{kb_id}")
    async def api_get_kbinfo(kb_id: str) -> dict:
        return await _get_kbinfo(kb_id)

    @app.get("/v1/kbs/files/{kb_id}")
    async def api_get_kb_files(kb_id: str) -> list[dict]:
        return await _get_kb_files(kb_id)

    @app.get("/v1/kbs/questions/{kb_id}")
    async def api_get_kb_questions(kb_id: str) -> list[str]:
        return await _get_kb_questions(kb_id)

    logger.info("Starting development server manually")
