## Plugins for OPEA & EKBA

### TEI plugin
Dify implemented a official [huggingface tei plugin](https://github.com/langgenius/dify-official-plugins/tree/main/models/huggingface_tei)

But it's not working well, we enabled TEI embedding and reranking based on Dify official plugin, and fixed issues.

### OpenVINO&trade; Model Server plugin

OpenVINO is an Open-source software toolkit for optimizing and deploying deep learning models.

OpenVINO&trade; Model Server (OVMS) is a high-performance system for serving models. Implemented in C++ for scalability and optimized for deployment on Intel architectures. It uses the same API as [TensorFlow Serving](https://github.com/tensorflow/serving) and [KServe](https://github.com/kserve/kserve) while applying OpenVINO for inference execution. Inference service is provided via gRPC or REST API, making deploying new algorithms and AI experiments easy.

#### Plugin Suppored features:
- **[NEW]** [Text Embeddings compatible with OpenAI API](https://github.com/openvinotoolkit/model_server/blob/main/demos/embeddings/README.md)
- **[NEW]** [Reranking compatible with Cohere API](https://github.com/openvinotoolkit/model_server/blob/main/demos/rerank/README.md)

### Plugin packaging

Dify docs portal lacks of correct packing tool & method, please follow steps 
- install [dify plugin tool](https://github.com/langgenius/dify-plugin-daemon/releases)
- package the plugin
  ```
  dify plugin package ./your_plugin_project
  ```
