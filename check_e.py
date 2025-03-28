import logging
import os
import common
import shutil


def check_and_del_data_include_null(task):
    # ???task
    school_id = task["school_id"]
    school = task["school"]
    teacher_id = task["teacher_id"]
    teacher_name = task["teacher_name"]

    # ???????·??
    path_school, path_school_teacher = common.make_path(school_id, school, teacher_id, teacher_name)

    # д??json
    if os.path.exists(path_school_teacher) and 'search_results_information_got.json' in os.listdir(str(path_school_teacher)):
        with open(os.path.join(path_school_teacher, 'search_results_information_got.json'), 'r',
                  encoding='utf-8') as file:
            for record in file.readlines():
                if "null" in record:
                    file.close()
                    logging.info(f"文件{path_school_teacher}被删了，因为含有null。")
                    shutil.rmtree(path_school_teacher)
                    return False
                if "[]" in record:
                    file.close()
                    shutil.rmtree(path_school_teacher)
                    logging.info(f"文件{path_school_teacher}被删了，因为含有[]。")
                    return False
    return True




