import logging
import os
from typing import Any, Dict, List, Optional
from app.utils.excel_reader import ExcelReader
from app.utils.excel_writer import ExcelWriter

logger = logging.getLogger(__name__)


class ExcelService:

    @staticmethod
    def read_params(file_path: str, param_column: str = None, start_row: int = 2, sheet_name: str = None) -> Dict[str, Any]:
        reader = ExcelReader(file_path)
        if not reader.load():
            raise ValueError(f"无法加载Excel文件: {file_path}")

        try:
            # 如果指定了sheet_name，切换到该sheet
            if sheet_name:
                reader.set_worksheet(sheet_name)

            file_info = reader.get_file_info()
            column_names = reader.get_column_names()

            if param_column:
                column_letter = reader.get_column_letter_by_name(param_column)
                if column_letter:
                    data = reader.get_column_data(column=column_letter, start_row=start_row)
                else:
                    data = reader.get_column_data(column=param_column, start_row=start_row)
            else:
                if column_names:
                    first_col = column_names[0]
                    column_letter = reader.get_column_letter_by_name(first_col)
                    data = reader.get_column_data(column=column_letter or 'A', start_row=start_row)
                else:
                    data = reader.get_column_data(column='A', start_row=start_row)

            validation = reader.validate_data(data)
            return {
                'file_info': file_info,
                'column_names': column_names,
                'data': data,
                'validation': validation,
            }
        finally:
            reader.close()

    @staticmethod
    def read_multiple_columns(file_path: str, columns: List[str], start_row: int = 2) -> Dict[str, Any]:
        reader = ExcelReader(file_path)
        if not reader.load():
            raise ValueError(f"无法加载Excel文件: {file_path}")

        try:
            data_dict = reader.get_multiple_columns(columns, start_row=start_row)
            file_info = reader.get_file_info()
            return {'file_info': file_info, 'data': data_dict}
        finally:
            reader.close()

    @staticmethod
    def write_results_to_existing(input_file: str, output_file: str,
                                   results: List[Dict[str, Any]],
                                   param_column_name: str,
                                   sheet_name: str = None) -> str:
        writer = ExcelWriter(output_file)

        if os.path.abspath(input_file) == os.path.abspath(output_file):
            if not writer.load_existing():
                raise ValueError(f"无法加载输入文件: {input_file}")
        else:
            import shutil
            shutil.copy2(input_file, output_file)
            if not writer.load_existing():
                raise ValueError(f"无法加载输出文件: {output_file}")

        try:
            if sheet_name:
                writer.create_sheet(sheet_name)

            writer.write_data_by_column_name(results, param_column_name)
            writer.save()
            return output_file
        finally:
            writer.close()

    @staticmethod
    def write_results_new(output_file: str, results: List[Dict[str, Any]],
                          sheet_name: str = '查询结果') -> str:
        writer = ExcelWriter(output_file)
        writer.create_new()

        try:
            writer.write_query_results(results, sheet_name=sheet_name)
            writer.save()
            return output_file
        finally:
            writer.close()

    @staticmethod
    def get_file_info(file_path: str) -> Dict[str, Any]:
        reader = ExcelReader(file_path)
        if not reader.load():
            return {}
        try:
            return reader.get_file_info()
        finally:
            reader.close()

    @staticmethod
    def get_column_names(file_path: str) -> list:
        reader = ExcelReader(file_path)
        if not reader.load():
            return []
        try:
            return reader.get_column_names()
        finally:
            reader.close()

    @staticmethod
    def get_all_sheets_info(file_path: str) -> list:
        reader = ExcelReader(file_path)
        if not reader.load():
            return []
        try:
            return reader.get_all_sheets_info()
        finally:
            reader.close()

    @staticmethod
    def parse_file(file_path: str, sheet_name: str = None, preview_rows: int = 5,
                   columns: List[str] = None, values_column: str = None,
                   max_values: int = 200) -> Dict[str, Any]:
        """解析Excel文件：返回工作表列表、当前工作表列名/行数及数据预览

        Args:
            values_column: 可选，需要提取「所有非空值」的列（表头名或列字母）
            max_values: values_column 最多返回的值个数
        """
        reader = ExcelReader(file_path)
        if not reader.load():
            raise ValueError(f"无法加载Excel文件: {file_path}")

        try:
            sheets = reader.get_all_sheets_info()
            if sheet_name:
                reader.set_worksheet(sheet_name)
            file_info = reader.get_file_info()
            preview = reader.get_preview_rows(limit=preview_rows, columns=columns)
            result = {
                'file_info': file_info,
                'sheets': sheets,
                'active_sheet': file_info.get('sheet_name'),
                'preview': preview,
            }
            if values_column:
                result['column_values'] = reader.get_column_values(values_column, limit=max_values)
            return result
        finally:
            reader.close()
