# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import json
import os
import shutil
import time
from typing import List, Dict, Optional, Union
import magic_pdf_parse_util
from ocr_text_splitter import OCRTextSplitter
from config import (
    COLLECTION_NAME,
    LOCAL_EMBEDDING_MODEL,
    MILVUS_HOST,
    MILVUS_PORT,
    MOSEC_EMBEDDING_ENDPOINT,
    MOSEC_EMBEDDING_MODEL,
    TEI_EMBEDDING_ENDPOINT,
    OVMS_EMBEDDING_ENDPOINT,
    OVMS_EMBEDDING_MODEL,
    embedding_ctx_length,
)
from fastapi import Body, File, Form, HTTPException, UploadFile
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceBgeEmbeddings, HuggingFaceHubEmbeddings, OpenAIEmbeddings
from langchain_core.documents import Document
from langchain_milvus.vectorstores import Milvus
from langchain_text_splitters import HTMLHeaderTextSplitter

from comps import CustomLogger, DocPath, opea_microservices, register_microservice
from comps.dataprep.utils import (
    create_upload_folder,
    document_loader,
    get_separators,
    save_content_to_local_disk, is_url, check_files, load_json_files,
)

MILVUS_URI = f"http://{MILVUS_HOST}:{MILVUS_PORT}"
CONNECTION_ARGS = {
    "uri": MILVUS_URI,
}

logger = CustomLogger("prepare_doc_milvus")
logflag = os.getenv("LOGFLAG", False)

# workaround notes: cp comps/dataprep/utils.py ./milvus/utils.py
# from utils import document_loader, get_tables_result, parse_html
index_params = {"index_type": "FLAT", "metric_type": "IP", "params": {}}
partition_field_name = "filename"
upload_folder = "./uploaded_files/"
link_type = 1
file_type = 0


class MosecEmbeddings(OpenAIEmbeddings):
    def _get_len_safe_embeddings(
            self, texts: List[str], *, engine: str, chunk_size: Optional[int] = None
    ) -> List[List[float]]:
        _chunk_size = chunk_size or self.chunk_size
        batched_embeddings: List[List[float]] = []
        response = self.client.create(input=texts, **self._invocation_params)
        if not isinstance(response, dict):
            response = response.model_dump()
        batched_embeddings.extend(r["embedding"] for r in response["data"])

        _cached_empty_embedding: Optional[List[float]] = None

        def empty_embedding() -> List[float]:
            nonlocal _cached_empty_embedding
            if _cached_empty_embedding is None:
                average_embedded = self.client.create(input="", **self._invocation_params)
                if not isinstance(average_embedded, dict):
                    average_embedded = average_embedded.model_dump()
                _cached_empty_embedding = average_embedded["data"][0]["embedding"]
            return _cached_empty_embedding

        return [e if e is not None else empty_embedding() for e in batched_embeddings]


def ingest_chunks_to_milvus(file_name: str, chunks: List[Union[str, dict]], collection_name: str, type: int):
    if logflag:
        logger.info(f"[ ingest chunks ] file name: {file_name}")
    s_time = time.time()
    # insert documents to Milvus
    insert_docs = []

    # Check the type of elements in chunks and process accordingly
    for chunk in chunks:
        if isinstance(chunk, dict):
            # If chunk is a dictionary (List[dict] case)
            text = chunk.get("text", "")
            metadata = chunk.get("metadata", {})
            metadata.setdefault(partition_field_name, file_name)  # Add partition field to metadata
        elif isinstance(chunk, str):
            text = chunk
            metadata = {partition_field_name: file_name}  # Metadata contains partition field only
        else:
            raise ValueError("Each chunk must be either a string or a dictionary with 'text' and 'metadata' keys.")
        metadata['type'] = type
        metadata.setdefault('extra_info', "")
        metadata.setdefault('rect', {})
        metadata.setdefault('page', {})
        insert_docs.append(Document(page_content=text, metadata=metadata))

    # Batch size
    batch_size = 32
    num_chunks = len(chunks)

    for i in range(0, num_chunks, batch_size):
        if logflag:
            logger.info(f"[ ingest chunks ] Current batch: {i}")
        batch_docs = insert_docs[i: i + batch_size]

        try:
            _ = Milvus.from_documents(
                batch_docs,
                embeddings,
                collection_name=collection_name,
                connection_args=CONNECTION_ARGS,
                partition_key_field=partition_field_name,
                index_params=index_params,
            )
        except ValueError as e:
            if logflag:
                logger.error(f"[ ingest chunks ] fail to ingest chunks into Milvus. error: {e}")
            continue
        except Exception as e:
            if logflag:
                logger.info(f"[ ingest chunks ] fail to ingest chunks into Milvus. error: {e}")
            raise HTTPException(status_code=500, detail=f"Fail to store chunks of file {file_name}.")
    e_time = time.time()
    if logflag:
        logger.info(f"[ ingest chunks ] Docs ingested file {file_name} to Milvus collection {collection_name}.")
        logger.info(f" ingest time:{e_time - s_time:.4f} seconds")

    return True


def ingest_data_to_milvus(doc_path: DocPath, type: int):
    """Ingest document to Milvus."""
    path = doc_path.path
    file_name = path.split("/")[-1]
    if logflag:
        logger.info(f"[ ingest data ] Parsing document {path}, file name: {file_name}.")

    if path.endswith(".html"):
        headers_to_split_on = [
            ("h1", "Header 1"),
            ("h2", "Header 2"),
            ("h3", "Header 3"),
        ]
        text_splitter = HTMLHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    elif path.endswith(".pdf"):
        # Initialize OCRTextSplitter for PDF OCR processing
        text_splitter = OCRTextSplitter(
            chunk_size=doc_path.chunk_size,
            chunk_overlap=doc_path.chunk_overlap,
            separator=" ",
            strip_whitespace=True
        )
    else:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=doc_path.chunk_size,
            chunk_overlap=doc_path.chunk_overlap,
            add_start_index=True,
            separators=get_separators(),
        )
    t1 = time.time()

    if path.endswith(".pdf"):
        pdf_mid_data, md_content = magic_pdf_parse_util.pdf_parse_main(pdf_path=path)
        pages_info = magic_pdf_parse_util.extract_page_info(pdf_mid_data)
        pretty_json = json.dumps(pages_info, ensure_ascii=False, indent=4)
        logger.info(f"pages_info: {pretty_json}")
        logger.info(f"md_content: {md_content}")
        content = md_content
        t2 = time.time()
        logger.info(f"==== pdf file, magic_pdf_parse_util")
    else:
        logger.info(f"==== not pdf files,document_loader")
        content = document_loader(path)

    t2 = time.time()
    logger.info(f"document_loader time:{t2 - t1:.4f} seconds")
    if logflag:
        logger.info("[ ingest data ] file content loaded")

    structured_types = [".xlsx", ".csv", ".json", "jsonl"]
    _, ext = os.path.splitext(path)

    if ext in structured_types:
        chunks = content
    elif path.endswith(".pdf"):
        chunks = text_splitter.split_text(pages_info)
    else:
        chunks = text_splitter.split_text(content)

    if logflag:
        logger.info(f"[ ingest data ] Done preprocessing. Created {len(chunks)} chunks of the original file.")

    return ingest_chunks_to_milvus(file_name, chunks, doc_path.collection_name, type)


def ingest_link_data_to_milvus(datasets: Dict, chunk_size: int, chunk_overlap: int, collection_name: str, type: int):
    """Ingest document for link data to Milvus."""
    if logflag:
        logger.info(f"[ ingest data ] file names: {datasets}.")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        add_start_index=True,
        separators=get_separators(),
    )
    t1 = time.time()
    contents = datasets
    t2 = time.time()
    logger.info(f"document_loader time:{t2 - t1:.4f} seconds")
    if logflag:
        logger.info("[ ingest data ] file content loaded")

    for source_filename, links_infos in contents.items():
        insert_data = []
        for link, info in links_infos.items():
            document = info
            content = document['content']
            chunks = text_splitter.split_text(content)
            document.pop('content')
            extra_info = json.dumps(document)
            insert_data.extend([{'metadata': {"extra_info": extra_info}, "text": chunk} for chunk in chunks])
        # If there is data to insert, call the function to ingest it into Milvus
        if len(insert_data) > 0:
            ingest_chunks_to_milvus(source_filename, insert_data, collection_name, type)


def search_by_file(collection, file_name):
    query = f"{partition_field_name} == '{file_name}'"
    results = collection.query(
        expr=query,
        output_fields=[partition_field_name, "pk"],
    )
    if logflag:
        logger.info(f"[ search by file ] searched by {file_name}")
        logger.info(f"[ search by file ] {len(results)} results: {results}")
    return results


async def search_by_type_and_delete(collection, type_value, json_data, batch_size=1000):
    """
        Perform batch queries on Milvus for data where type == type_value,
        compare the source_url in json_data, and if a match is found, record the pk of the matching data.
        Then, delete these matched records in each batch.

        Arguments:
            collection: Milvus database operation object
            type_value: The type value to query (e.g., 1)
            json_data: A dictionary returned by load_json_files, with source_url as keys
            batch_size: The number of records to query per batch (default is 1000)
    """
    query = f"type == {type_value}"
    offset = 0
    try:
        while True:
            # Execute the query to get matching records
            results = collection.query(
                expr=query,
                output_fields=["extra_info", "filename", "pk"],
                limit=batch_size,
                offset=offset
            )
            if not results:
                break  # Exit the loop when there are no more results
            # Collect the pks of matched records in this batch
            pks_to_delete = []
            for item in results:
                # Attempt to parse the extra_info field as JSON
                try:
                    extra_info = json.loads(item.get("extra_info", "{}"))
                except Exception as e:
                    extra_info = {}
                    if logflag:
                        logger.error(f"[ search by type ] Failed to parse extra_info: {str(e)}")

                source_url = extra_info.get("source_url")
                if source_url:
                    # If the current source_url is found in json_data, it is considered a match, record the pk
                    if source_url in json_data:
                        pks_to_delete.append(item.get("pk"))
            offset += batch_size
            if logflag:
                logger.info(
                    f"[ search by type ] Batch query: {len(results)} records retrieved (offset: {offset})"
                )
            # If there are matched records in this batch, delete them
            if pks_to_delete:
                try:
                    expr = f'pk in {pks_to_delete}'
                    collection.delete(expr)
                    if logflag:
                        logger.info(f"[ search by type ] Deleted {len(pks_to_delete)} matching records in this batch")
                except Exception as e:
                    logger.error(f"[ search by type ] Deletion failed: {str(e)}")
                    raise HTTPException(status_code=500, detail="Failed when searching in Milvus db for all files.")

    except Exception as e:
        logger.error(f"[ search by type ] Query failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Query failed，because {str(e)}")


def search_all(collection):
    results = collection.query(expr="pk >= 0", output_fields=[partition_field_name, "pk"])
    if logflag:
        logger.info(f"[ search all ] {len(results)} results: {results}")
    return results


def delete_all_data(my_milvus):
    if logflag:
        logger.info("[ delete all ] deleting all data in milvus")
    if my_milvus.col:
        my_milvus.col.drop()
    if logflag:
        logger.info("[ delete all ] delete success: all data")


def delete_by_partition_field(my_milvus, partition_field):
    if logflag:
        logger.info(f"[ delete partition ] deleting {partition_field_name} {partition_field}")
    pks = my_milvus.get_pks(f'{partition_field_name} == "{partition_field}"')
    if logflag:
        logger.info(f"[ delete partition ] target pks: {pks}")
    res = my_milvus.delete(pks)
    my_milvus.col.flush()
    if logflag:
        logger.info(f"[ delete partition ] delete success: {res}")


def get_files_from_collection(milvus_obj: Milvus) -> List[Dict[str, str]]:
    """
    Check if the collection exists and retrieve all files from the database.

    Args:
        milvus_obj: An instance of the Milvus class.

    Returns:
        A list of file information dictionaries.
    """
    if not milvus_obj.col:
        logger.info(f"[ get_files_from_collection ] collection {milvus_obj.collection_name} does not exist.")
        return []

    try:
        all_data = search_all(milvus_obj.col)
    except Exception as e:
        logger.error(f"[ get_files_from_collection ] Error while searching: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed when searching in Milvus db for all files.")

    if len(all_data) == 0:
        return []

    res_file = [res["filename"] for res in all_data]
    unique_list = list(set(res_file))
    if logflag:
        logger.info(f"[ get_files_from_collection ] unique list from db: {unique_list}")

    file_list = [
        {
            "name": file_name,
            "id": file_name,
            "type": "File",
            "parent": "",
        }
        for file_name in unique_list
    ]

    return file_list


def delete_file_and_folder(upload_folder: str, file_name: str):
    """
    Deletes a file and its corresponding folder (if exists) from the upload folder.

    Args:
        upload_folder (str): The path to the upload folder.
        file_name (str): The name of the file to be deleted.

    Raises:
        HTTPException: If the file or folder cannot be deleted.
    """
    file_path = os.path.join(upload_folder, file_name)
    folder_path = os.path.join(upload_folder, os.path.splitext(file_name)[0])

    try:
        # Delete the file if it exists
        if os.path.exists(file_path):
            os.remove(file_path)
            if logflag:
                logger.info(f"[ delete ] Successfully deleted file {file_path}.")

        # Delete the folder if it exists
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            shutil.rmtree(folder_path)
            if logflag:
                logger.info(f"[ delete ] Successfully deleted folder {folder_path}.")

        return True
    except Exception as e:
        if logflag:
            logger.info(f"[ delete ] {e}. Failed to delete file or folder for {file_name}.")
        return False


@register_microservice(name="opea_service@prepare_doc_milvus", endpoint="/v1/dataprep", host="0.0.0.0", port=6010)
async def ingest_documents(
        files: Optional[Union[UploadFile, List[UploadFile]]] = File(None),
        link_list: Optional[str] = Form(None),
        chunk_size: int = Form(1000),
        chunk_overlap: int = Form(100),
        process_table: bool = Form(False),
        table_strategy: str = Form("fast"),
        pdf_ocr_type: Optional[int] = Form(-1),  # 0: Auto, 1:Puretext  2: pdfplumber 3:paddleOCR
        collection_name: str = Form(COLLECTION_NAME)  # Add collection_name parameter with default value
):
    if logflag:
        logger.info(f"[ upload ] files:{files}")
        logger.info(f"[ upload ] link_list:{link_list}")
        # log all the input parameters
        logger.info(
            f"... chunk_size={chunk_size},chunk_overlap={chunk_overlap},process_table={process_table},table_strategy={table_strategy},pdf_ocr_type={pdf_ocr_type}")

    if files and link_list:
        raise HTTPException(status_code=400, detail="Provide either a file or a string list, not both.")

    # define Milvus obj
    my_milvus = Milvus(
        embedding_function=embeddings,
        collection_name=collection_name,
        connection_args=CONNECTION_ARGS,
        index_params=index_params,
        auto_id=True,
        enable_dynamic_field=True,
    )

    if files:
        if not isinstance(files, list):
            files = [files]
        uploaded_files = []

        for file in files:
            encode_file = file.filename
            save_path = upload_folder + encode_file
            if logflag:
                logger.info(f"[ upload ] processing file {save_path}")

            if my_milvus.col:
                # check whether the file is already uploaded
                try:
                    search_res = search_by_file(my_milvus.col, encode_file)
                except Exception as e:
                    raise HTTPException(
                        status_code=500, detail=f"Failed when searching in Milvus db for file {file.filename}."
                    )
                if len(search_res) > 0:
                    if logflag:
                        logger.info(f"[ upload ] File {file.filename} already exists.")
                    raise HTTPException(
                        status_code=400,
                        detail=f"Uploaded file {file.filename} already exists. Please change file name.",
                    )

            result = await save_content_to_local_disk(save_path, file)

            if result["status"] != "success":
                raise HTTPException(status_code=result["status"], detail=result["message"])

            ingest_data_to_milvus(
                DocPath(
                    path=save_path,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    process_table=process_table,
                    table_strategy=table_strategy,
                    pdf_ocr_type=pdf_ocr_type,
                    collection_name=collection_name,
                ),
                type=0
            )
            uploaded_files.append(save_path)
            if logflag:
                logger.info(f"Saved file {save_path} into local disk.")

        results = {"status": 200, "message": "Data preparation succeeded"}
        if logflag:
            logger.info(results)
        return results

    if link_list:
        link_list = json.loads(link_list)  # Parse JSON string to list
        if not isinstance(link_list, list):
            raise HTTPException(status_code=400, detail="link_list should be a list.")
        # Check if the files corresponding to the links exist
        filenames = [link.replace("/", "%2F") + ".json" for link in link_list]
        existing_files, missing_files = await check_files(upload_folder, filenames)
        # First stage of data preprocessing (filter out duplicate URLs from the files to be loaded)
        dataset, file_level_dataset = await load_json_files(upload_folder, existing_files)
        # Second stage of data preprocessing (delete URLs that already exist in Milvus from the files to be loaded)
        if my_milvus.col:
            try:
                await search_by_type_and_delete(my_milvus.col, link_type, dataset, 1000)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed when searching in Milvus db for link_type .")
        # Ingest the preprocessed data into Milvus
        ingest_link_data_to_milvus(
            datasets=file_level_dataset,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            collection_name=collection_name,
            type=1
        )
        return {"status": 200, "message": "Data preparation success"}

    raise HTTPException(status_code=400, detail="Must provide either a file or a string list.")


@register_microservice(
    name="opea_service@prepare_doc_milvus", endpoint="/v1/dataprep/get_file", host="0.0.0.0", port=6010
)
async def rag_get_file_structure(collection_name: str = Body(COLLECTION_NAME, embed=True)):
    if logflag:
        logger.info("[ get ] start to get file structure")

    # define Milvus obj
    my_milvus = Milvus(
        embedding_function=embeddings,
        collection_name=collection_name,
        connection_args=CONNECTION_ARGS,
        index_params=index_params,
        auto_id=True,
    )

    file_list = get_files_from_collection(my_milvus)

    if logflag:
        logger.info(f"[ get ] final file list: {file_list}")
    return file_list


@register_microservice(
    name="opea_service@prepare_doc_milvus", endpoint="/v1/dataprep/delete_file", host="0.0.0.0", port=6010
)
async def delete_single_file(
        file_path: str = Body(..., embed=True),
        collection_name: str = Body(COLLECTION_NAME, embed=True),
):
    """Delete file according to `file_path`.

    `file_path`:
        - file/link path (e.g. /path/to/file.txt)
        - "all": delete all files uploaded
    """
    if logflag:
        logger.info(file_path)

    # define Milvus obj
    my_milvus = Milvus(
        embedding_function=embeddings,
        collection_name=collection_name,
        connection_args=CONNECTION_ARGS,
        index_params=index_params,
        auto_id=True,
    )

    # delete all uploaded files
    if file_path == "all":
        if logflag:
            logger.info("[ delete ] deleting all files")

        file_list = get_files_from_collection(my_milvus)
        delete_all_data(my_milvus)

        all_successful = True
        # Delete files and corresponding folders on local disk
        for file in file_list:
            success = delete_file_and_folder(upload_folder, file["name"])
            if not success:
                all_successful = False
                if logflag:
                    logger.warning(f"[ delete ] Failed to delete file or folder for {file['name']}.")

        if all_successful:
            if logflag:
                logger.info("[ delete ] successfully deleted all files and folders from file list.")
        else:
            if logflag:
                logger.warning("[ delete ] Some files or folders could not be deleted.")

        return {"status": all_successful}

    try:
        if is_url(file_path):
            file_path = file_path.replace("/", "%2F")
            delete_by_partition_field(my_milvus, file_path)
    except Exception as e:
        if logflag:
            logger.info(f"[delete] failed to delete record {file_path} from the database: {e}")
        return {"status": False}

    success = delete_file_and_folder(upload_folder, file_path)

    if not success:
        if logflag:
            logger.warning(f"[ delete ] Failed to delete file or folder for {file['name']}.")
        return {"status": False}

    if logflag:
        logger.info(f"[delete] successfully deleted file: {file_path}")
    return {"status": True}


@register_microservice(
    name="opea_service@prepare_doc_milvus", endpoint="/v1/dataprep/get_collections", host="0.0.0.0", port=6010
)
async def get_collections():
    from pymilvus import connections, utility
    try:
        connections.connect("default", **CONNECTION_ARGS)
        collections = utility.list_collections()
        if logflag:
            for collection in collections:
                logger.info(f"[get_collections] {collection}")
    except Exception as e:
        print(f"Error retrieving collections: {e}")
        return []
    return utility.list_collections()


@register_microservice(
    name="opea_service@prepare_doc_milvus", endpoint="/v1/dataprep/get_questionlist", host="0.0.0.0", port=6010
)
async def get_questionlist(collection_name: str = Body(COLLECTION_NAME, embed=True)):
    # hardcode here, remove this function in the future.
    questionlist_file_path = upload_folder + "questionlist.json"
    if not os.path.exists(questionlist_file_path):
        logger.warning(f"Can't find file {questionlist_file_path}")
        return []

    collection_questions = []
    with open(questionlist_file_path, 'r', encoding='utf-8') as file:
        all_questions = json.load(file)
        if collection_name in all_questions and "questions" in all_questions[collection_name]:
            collection_questions = all_questions[collection_name]["questions"]
            logger.info("Get question lists.")
        else:
            logger.warning("No questionlist found!")

    return collection_questions


if __name__ == "__main__":
    create_upload_folder(upload_folder)

    # Create vectorstore
    if OVMS_EMBEDDING_ENDPOINT:
        from langchain_openai import OpenAIEmbeddings

        # Create an instance of OpenAIEmbedding
        embeddings = OpenAIEmbeddings(
            model=OVMS_EMBEDDING_MODEL,
            api_key="unused",
            base_url=OVMS_EMBEDDING_ENDPOINT,
            tiktoken_enabled=False,
            embedding_ctx_length=embedding_ctx_length,
        )
        if logflag:
            logger.info(f"OVMS_EMBEDDING_MODEL:{embeddings}")
    elif TEI_EMBEDDING_ENDPOINT:
        # create embeddings using TEI endpoint service
        if logflag:
            logger.info(f"[ prepare_doc_milvus ] TEI_EMBEDDING_ENDPOINT:{TEI_EMBEDDING_ENDPOINT}")
        embeddings = HuggingFaceHubEmbeddings(model=TEI_EMBEDDING_ENDPOINT)
    elif MOSEC_EMBEDDING_ENDPOINT:
        # create embeddings using MOSEC endpoint service
        if logflag:
            logger.info(
                f"[ prepare_doc_milvus ] MOSEC_EMBEDDING_ENDPOINT:{MOSEC_EMBEDDING_ENDPOINT}, MOSEC_EMBEDDING_MODEL:{MOSEC_EMBEDDING_MODEL}"
            )
        embeddings = MosecEmbeddings(model=MOSEC_EMBEDDING_MODEL)
    else:
        # create embeddings using local embedding model
        if logflag:
            logger.info(f"[ prepare_doc_milvus ] LOCAL_EMBEDDING_MODEL:{LOCAL_EMBEDDING_MODEL}")
        embeddings = HuggingFaceBgeEmbeddings(model_name=LOCAL_EMBEDDING_MODEL)

    opea_microservices["opea_service@prepare_doc_milvus"].start()
