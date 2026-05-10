import re
import json
import os
from docx import Document

def extract_3500_chars(file_path):
    if not file_path.endswith('.docx'):
        print("❌ 错误：请先将文件另存为 .docx 格式！")
        return

    print(f"🔍 正在处理: {file_path}")
    doc = Document(file_path)
    # 合并所有段落文本
    full_text = "".join([p.text for p in doc.paragraphs])
    
    # 根据文档中的标识符分割字表 [cite: 661, 734]
    if "字表二（1000）" in full_text:
        parts = full_text.split("字表二（1000）")
        list1_raw = parts[0]
        list2_raw = parts[1]
    else:
        list1_raw = full_text
        list2_raw = ""

    # 正则只提取汉字，过滤掉数字、字母和标点 [cite: 661-665]
    def get_only_chinese(text):
        return [char for char in text if '\u4e00' <= char <= '\u9fa5']

    data = {
        "common_list_1": get_only_chinese(list1_raw), # 对应 2500 字表 [cite: 661]
        "common_list_2": get_only_chinese(list2_raw), # 对应 1000 字表 [cite: 734]
        "metadata": "义务教育语文课程常用字表（3500字）"
    }

    output_file = "chars_3500.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✨ 转换成功！")
    print(f"📊 字表一（基础）：{len(data['common_list_1'])} 字")
    print(f"📊 字表二（进阶）：{len(data['common_list_2'])} 字")
    print(f"📂 已保存至: {os.path.abspath(output_file)}")

if __name__ == "__main__":
    # 请确保文件名与你本地另存为后的名称一致
    target_file = "3500个常用汉字整理完整讲解.docx"
    extract_3500_chars(target_file)