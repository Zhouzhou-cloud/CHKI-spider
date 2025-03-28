"""
encoding="UTF-8"

"""

import logging
import time
import common
import pandas as pd

# 月份
month_dic = {
    "January": "01",
    "February": "02",
    "March": "03",
    "April": "04",
    "May": "05",
    "June": "06",
    "July": "07",
    "August": "08",
    "September": "09",
    "October": "10",
    "November": "11",
    "December": "12",
}


def make_task_list(task_file_path):

    # 读取文件
    df = pd.read_excel(
        task_file_path,
        sheet_name="Sheet1",
        header=0,
        keep_default_na=False,
        dtype=str,
    )

    # 获得excel文件
    excel_list = []
    # 制作任务列表
    task_list = []
    try:
        for i in range(0, len(df)):
            paper_title = df.iloc[i]["论文名"].strip(" ")
            excel_list.append(
                {
                    "paper_title": paper_title,
                }
            )
        logging.info(f"任务是paper形")
        return "paper",excel_list
    except KeyError:
        try:
            # 目前剩下来的肯定都有学校，所以判断是否有教师
            # 如果无教师就是按学校-年份搜索
            # 如果有教师就是按学校-教师搜索
            for i in range(0, len(df)):
                school_id = df.iloc[i]["学校ID"].strip(" ")
                school = df.iloc[i]["学校"].strip(" ")
                teacher_id = df.iloc[i]["教师ID"].strip(" ")
                teacher_name = df.iloc[i]["教师姓名"].strip(" ")
                excel_list.append(
                    {
                        "school_id": school_id,
                        "school": school,
                        "teacher_id": teacher_id,
                        "teacher_name": teacher_name,
                    }
                )
            logging.info(f"任务是school-teacher形")
            return "school-teacher", excel_list
        except KeyError:
            # 那就是没有教师
            # 按学校-年搜索
            try:
                for i in range(0, len(df)):
                    school_id = df.iloc[i]["学校ID"].strip(" ")
                    school = df.iloc[i]["学校"].strip(" ")
                    year_start = df.iloc[i]["开始时间"].strip(" ")
                    year_end = df.iloc[i]["结束时间"].strip(" ")
                    excel_list.append(
                        {
                            "school_id": school_id,
                            "school": school,
                            "year_start": year_start,
                            "year_end": year_end
                        }
                    )
                for onepiece in excel_list:
                    # 按学校搜索，必须限定年份;由于学校-年搜索结果太大，所以必须按月份进行搜索
                    for year in range(int(onepiece["year_start"]), int(onepiece["year_end"]) + 1):
                        for month_key, month_value in month_dic.items():
                            # 获取该年该月的最后一天
                            date_start, date_end = common.return_search_date(int(year), int(month_value))
                            task = {
                                "school_id": onepiece["school_id"],
                                "school_name": onepiece["school"],
                                "year": year,
                                "month_key": month_key,
                                "month_value": month_value,
                                "start_search_time": date_start,
                                "end_search_time": date_end,
                            }
                            task_list.append(task)
                logging.info(f"任务是school-year-month形")
                return "school-year-month", task_list
            except KeyError:
                logging.error(f"未获得返回任务列表")
                return False