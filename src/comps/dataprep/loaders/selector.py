# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from comps.dataprep.loaders.aliyun_loader import OpGuidePdfDataAliyunLoader, ERDPdfDataAliyunLoader
from comps.dataprep.loaders.loader import SOPPdfDataLoader, RISKExcelDataLoader, \
    OpGuideWordDataLoader, OpGuidePdfDataLoader, ERDWordDataLoader, ERDPdfDataLoader, SopExcelDataUniversalLoader


async def get_loader(file_type: str, file_ext: str, loader_type:str):
    """
    根据 file_type + 扩展名 返回对应加载器实例
    """
    if loader_type == "aliyun":
        loader_class = ALIYUN_DATA_LOADER_REGISTRY.get((file_type.lower(), file_ext.lower()))
    else:
        loader_class = DATA_LOADER_REGISTRY.get((file_type.lower(), file_ext.lower()))
    if not loader_class:
        raise ValueError(f"不支持的文件类型或格式: 类型：{file_type}, 扩展名：{file_ext}")
    return loader_class()

DATA_LOADER_REGISTRY = {
    # SOP
    ("sop", "xlsx"): SopExcelDataUniversalLoader,
    ("sop", "xls"): SopExcelDataUniversalLoader,
    ("sop", "pdf"): SOPPdfDataLoader,

    # RISK
    ("risk", "xlsx"): RISKExcelDataLoader,
    ("risk", "xls"): RISKExcelDataLoader,

    # Operation Guide
    ("operation", "doc"): OpGuideWordDataLoader,
    ("operation", "docx"): OpGuideWordDataLoader,
    ("operation", "pdf"): OpGuidePdfDataLoader,

    # ERD
    ("emergency_drill", "doc"): ERDWordDataLoader,
    ("emergency_drill", "docx"): ERDWordDataLoader,
    ("emergency_drill", "pdf"): ERDPdfDataLoader,
}

ALIYUN_DATA_LOADER_REGISTRY = {
    # SOP
    ("sop", "xlsx"): SopExcelDataUniversalLoader,
    ("sop", "xls"): SopExcelDataUniversalLoader,
    ("sop", "pdf"): SOPPdfDataLoader,

    # RISK
    ("risk", "xlsx"): RISKExcelDataLoader,
    ("risk", "xls"): RISKExcelDataLoader,

    # Operation Guide
    ("operation", "doc"): OpGuideWordDataLoader,
    ("operation", "docx"): OpGuideWordDataLoader,
    ("operation", "pdf"): OpGuidePdfDataAliyunLoader,

    # ERD
    ("emergency_drill", "doc"): ERDWordDataLoader,
    ("emergency_drill", "docx"): ERDWordDataLoader,
    ("emergency_drill", "pdf"): ERDPdfDataAliyunLoader,
}


# if __name__ == "__main__":
    # 初始化 embeddings（使用已有的配置）
    # embeddings = HuggingFaceHubEmbeddings(
    #     model="http://10.3.70.118:13020/embed",
    #     huggingfacehub_api_token="dummy"
    # )
    # loader = SOPPdfDataLoader()
    # data = loader.load_data("配料集操布料小车手动操作SOP.pdf")
    # loader = SOPExcelDataLoader()
    # data = loader.load_data("合浦光玻厂-设备维保工段-机械检修技工-SOP-01设备检修标准作业卡-焊接.xlsx")
    # loader = RISKExcelDataLoader()
    # data = loader.load_data("配料集操工事故案例和风险辨识卡.xlsx")
    # loader = OpGuideWordDataLoader()
    # data = loader.load_data("包装岗位操作规程.docx")
    # data = loader.load_data("2025.2原料工区铲车伤人应急预案演练.doc")
    # loader = OpGuidePdfDataLoader()
    # data = loader.load_data("原料工区操作规程（配料集操工）.pdf",embeddings=embeddings)
    # loader = ERDWordDataLoader()
    # data = loader.load_data("2025.1原料工区触电事故应急预案演练.doc")
    # data = loader.load_data("2025.2原料工区铲车伤人应急预案演练123.doc")
    # data = loader.load_data(file_path="test1.docx")
    # loader = ERDPdfDataLoader()
    # data = loader.load_data("2025.2原料工区铲车伤人应急预案演练.pdf")
    # data = loader.load_data("2025.1原料工区触电事故应急预案演练.pdf")
    # print(data)
