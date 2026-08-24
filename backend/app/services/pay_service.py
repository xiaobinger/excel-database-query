"""代付提现服务

集成原"代付提现"桌面工具的 4 个渠道逻辑：
- 合利宝(helipay)：代付
- 电银(dianyin)：代付 / 查询
- 乐商通PLUS(lepass)：代付(实时) / 查询
- 快乐刷(kls)：实时代付 / 跑批代付(创建/查询/发起提现) / 查询

Excel 列映射（固定列索引，从 0 开始）：
  row[2]=姓名 accountName, row[3]=流水号 businessNo, row[4]=手机号,
  row[5]=身份证号 idCardNo, row[6]=银行卡号 bankCardNo,
  row[8]=金额(分) amount, row[12]=子代理编号 objectDstId,
  row[13]=提现applyId, row[14]=代付响应/reqId, row[15]=提现响应,
  row[16]=查询响应, row[17]=提现响应
"""
import json
import random
import string
import time
import hashlib
import requests
from openpyxl import load_workbook, Workbook


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _cell(row, idx):
    """安全读取行数据（不足列数返回 None）"""
    if idx < len(row):
        v = row[idx]
        return v
    return None


def _to_str(v):
    if v is None:
        return ''
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _to_int(v):
    try:
        return int(float(v))
    except Exception:
        return 0


def format_amount_to_yuan(amount_fen):
    return "{:.2f}".format(amount_fen / 100)


def generate_unique_id(merchant_id, length=32):
    timestamp = int(time.time())
    characters = string.ascii_letters + string.digits
    random_part = ''.join(random.choices(characters, k=length - len(str(timestamp)) - len(str(merchant_id))))
    return f"{merchant_id}{timestamp}{random_part}"


def _load_rows(file_path):
    """读取 Excel 数据行（跳过表头），返回 list[list]"""
    wb = load_workbook(file_path, data_only=True)
    ws = wb.active
    rows = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if all(c is None or str(c).strip() == '' for c in row):
            continue
        rows.append(list(row))
    return rows


def _write_result(file_path, rows, result_rows, sheet_name='代付结果'):
    """生成结果 Excel：原始列 + 结果列，返回新文件路径"""
    import os
    out_path = file_path + '_result.xlsx'
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    # 表头：原始表头无法直接获取（已跳过），用列序号占位 + 结果列
    ws.append([f'列{i+1}' for i in range(len(rows[0])) if rows[0]] + ['子代理编号', 'applyId', '代付响应', '提现响应', '查询响应', '提现查询响应'])
    for r in result_rows:
        ws.append(r)
    wb.save(out_path)
    return out_path


def _post_json(url, payload, timeout=30):
    resp = requests.post(url, json=payload, timeout=timeout)
    return resp


# ---------------------------------------------------------------------------
# 合利宝
# ---------------------------------------------------------------------------

def helipay_pay(cfg, rows, params, log):
    success, fail, success_amount = 0, 0, 0
    result_rows = []
    for row in rows:
        business_no = _to_str(_cell(row, 3))
        account_name = _to_str(_cell(row, 2))
        bank_card_no = _to_str(_cell(row, 6))
        amount_fen = _to_int(_cell(row, 8))
        amount_yuan = format_amount_to_yuan(amount_fen)

        payload = {
            'agentNo': cfg.get('agentNo'),
            'data': {
                'agentNo': cfg.get('agentNo'),
                'userId': cfg.get('userId'),
                'withdrawAmount': amount_yuan,
                'cardNo': bank_card_no,
                'payerName': account_name,
                'bankCode': params.get('bank_code', 'CCB'),
                'orderNum': business_no,
                'onlineBankType': params.get('online_bank_type', 'B2C'),
            },
            'userId': cfg.get('userId'),
            'url': cfg.get('helipayUrl', '') + '/mpos-trx/rest/withdraw/agentApply.action',
        }
        try:
            resp = _post_json(cfg.get('baseUrl', '') + '/test/heliPay/sendRequest', payload)
            text = resp.text
            result_json = json.loads(text)
            if result_json.get('retCode') == '0000':
                success += 1
                success_amount += amount_fen
                resp_str = '成功'
            else:
                fail += 1
                resp_str = text[:500]
            log(f'合利宝 流水{business_no} 金额{amount_yuan}元 => {resp_str}')
        except Exception as e:
            fail += 1
            resp_str = f'异常: {e}'
            log(f'合利宝 流水{business_no} 异常: {e}')
        result_rows.append(row + ['' , '', resp_str, '', '', ''])
    message = f'合利宝代付成功：{success}笔, 失败：{fail}笔, 成功金额：{format_amount_to_yuan(success_amount)}元'
    return message, result_rows


# ---------------------------------------------------------------------------
# 电银
# ---------------------------------------------------------------------------

def _dianyin_sign(json_obj, key):
    data = json.loads(json_obj) if isinstance(json_obj, str) else dict(json_obj)
    sorted_data = dict(sorted(data.items()))
    result = "&".join([f"{k}={v}" for k, v in sorted_data.items()])
    result = result + "key=" + key
    return hashlib.sha256(result.encode('utf-8')).hexdigest()


def _dianyin_request(cfg, url, signature, param_json):
    headers = {'Content-Type': 'application/json', 'signature': signature}
    return requests.post(url, data=param_json, headers=headers, timeout=30)


def dianyin_withdraw(cfg, order_no, amount, account_json):
    """账户报备 + 发起提现"""
    account_report_obj = json.loads(account_json)
    account_report_obj["drawType"] = 'FROZEN'
    account_report_obj["partnerIden"] = 'dyin'
    account_report_obj["channelNo"] = cfg.get('channelNo', '81429675')
    account_report_obj["partnerNo"] = cfg.get('partnerNo', '88805')
    account_report_obj = json.dumps(account_report_obj)

    account_report_url = cfg.get('accountReportUrl', 'http://39.101.182.160:8070/api/with-draw/account-contract')
    account_report_sign = _dianyin_sign(account_report_obj, cfg.get('signKey', ''))
    account_report_result = _dianyin_request(cfg, account_report_url, account_report_sign, account_report_obj)

    if account_report_result.status_code == 200:
        account_report_json = account_report_result.json()
        if account_report_json.get("code") == 200:
            account_id = account_report_json["data"]["accId"]
            withdraw_obj = {
                "accId": account_id,
                "amount": amount,
                "asSupportInvoice": "N",
                "channelNo": cfg.get('channelNo', '81429675'),
                "drawType": "FROZEN",
                "orderNo": order_no,
                "partnerIden": "dyin",
                "partnerNo": cfg.get('partnerNo', '88805'),
            }
            withdraw_url = cfg.get('withdrawUrl', 'http://39.101.182.160:8070/api/with-draw/with-draw')
            withdraw_result = _dianyin_request(cfg, withdraw_url, _dianyin_sign(json.dumps(withdraw_obj), cfg.get('signKey', '')), json.dumps(withdraw_obj))
            if withdraw_result.json().get("code") == 200 and withdraw_result.json().get("data", {}).get("orderStatus") == 'ONTHEWAY':
                return True
            return False
        return False
    return False


def dianyin_query(cfg, order_no):
    query_obj = {
        "channelNo": cfg.get('channelNo', '81429675'),
        "orderNo": order_no,
        "partnerIden": "dyin",
        "partnerNo": cfg.get('partnerNo', '88805'),
    }
    query_url = cfg.get('queryUrl', 'http://39.101.182.160:8070/api/with-draw/order-query')
    return _dianyin_request(cfg, query_url, _dianyin_sign(json.dumps(query_obj), cfg.get('signKey', '')), json.dumps(query_obj))


def dianyin_pay(cfg, rows, params, log):
    success, fail, success_amount = 0, 0, 0
    result_rows = []
    for row in rows:
        amount = _to_str(_cell(row, 8))
        order_no = _to_str(_cell(row, 3))
        id_name = _to_str(_cell(row, 2))
        bank_phone = _to_str(_cell(row, 4))
        bank_account = _to_str(_cell(row, 6))
        id_card_no = _to_str(_cell(row, 5))
        account_report_obj = {
            "bankAccount": bank_account,
            "bankCityCode": cfg.get('bankCityCode', '371700'),
            "bankDistrictCode": cfg.get('bankDistrictCode', '371702'),
            "bankPhone": bank_phone,
            "bankProvinceCode": cfg.get('bankProvinceCode', '370000'),
            "branchName": cfg.get('branchName', '中国工商银行'),
            "idCardNo": id_card_no,
            "idName": id_name,
        }
        try:
            flag = dianyin_withdraw(cfg, order_no, amount, json.dumps(account_report_obj, ensure_ascii=False))
            if flag:
                success += 1
                success_amount += _to_int(amount)
                resp_str = '成功'
            else:
                fail += 1
                resp_str = '报备/提现失败'
            log(f'电银 流水{order_no} 金额{format_amount_to_yuan(_to_int(amount))}元 => {resp_str}')
        except Exception as e:
            fail += 1
            resp_str = f'异常: {e}'
            log(f'电银 流水{order_no} 异常: {e}')
        result_rows.append(row + ['', '', resp_str, '', '', ''])
    message = f'电银代付成功：{success}笔, 金额：{format_amount_to_yuan(success_amount)}元, 失败：{fail}笔'
    return message, result_rows


def dianyin_query_batch(cfg, rows, params, log):
    success, fail, paying = 0, 0, 0
    fail_flows = ''
    result_rows = []
    for row in rows:
        order_no = _to_str(_cell(row, 3))
        try:
            result = dianyin_query(cfg, order_no)
            data = result.json()
            if data.get("code") == 200:
                status = data.get("data", {}).get("orderStatus")
                if status == 'SUCCESS':
                    success += 1
                    resp_str = '成功'
                elif status == 'FAIL':
                    fail += 1
                    fail_flows += f'{order_no}({data.get("data", {}).get("remitMsg")}), '
                    resp_str = f'失败: {data.get("data", {}).get("remitMsg")}'
                else:
                    paying += 1
                    resp_str = f'打款中: {status}'
            else:
                fail += 1
                fail_flows += f'{order_no}({data.get("msg")}), '
                resp_str = f'查询失败: {data.get("msg")}'
            log(f'电银查询 流水{order_no} => {resp_str}')
        except Exception as e:
            fail += 1
            resp_str = f'异常: {e}'
            log(f'电银查询 流水{order_no} 异常: {e}')
        result_rows.append(row + ['', '', '', '', resp_str, ''])
    message = f'电银代付成功：{success}笔, 失败：{fail}笔, 失败流水：{fail_flows}, 打款中：{paying}笔'
    return message, result_rows


# ---------------------------------------------------------------------------
# 乐商通PLUS / 快乐刷（共用 external-api 接口）
# ---------------------------------------------------------------------------

def _get_sub_agent_id(cfg, bank_card_no, channel_code):
    url = cfg.get('getSubAgentIdUrl', '')
    payload = {"bankCardNo": bank_card_no, "channelCode": channel_code}
    resp = requests.post(url, json=payload, timeout=30)
    return resp.text.strip()


def _lsp_transfer(cfg, business_no, object_dst_id, amount, transfer_mode):
    payload = {
        "source": cfg.get("source"),
        "objectSrcId": cfg.get("objectSrcId"),
        "objectDstId": object_dst_id,
        "amount": amount,
        "transferMode": transfer_mode,
        "key": cfg.get("key"),
        "businessNo": business_no,
        "sign": cfg.get("sign"),
    }
    return _post_json(cfg.get("baseUrl", '') + '/external-api/behalfPay/transfer', payload).text


def _lsp_create_pay(cfg, business_no, object_dst_id, amount, busi_type):
    payload = {
        "source": cfg.get("source"),
        "agentId": cfg.get("objectSrcId"),
        "subAgentId": object_dst_id,
        "amount": amount,
        "busiType": busi_type,
        "key": cfg.get("key"),
        "reqId": business_no,
        "sign": cfg.get("sign"),
    }
    return _post_json(cfg.get("baseUrl", '') + '/external-api/behalfPay/bPay', payload).text


def _lsp_query_pay(cfg, req_id, busi_type):
    payload = {
        "source": cfg.get("source"),
        "agentId": cfg.get("objectSrcId"),
        "busiType": busi_type,
        "key": cfg.get("key"),
        "reqId": req_id,
        "sign": cfg.get("sign"),
    }
    return _post_json(cfg.get("baseUrl", '') + '/external-api/behalfPay/queryV2', payload).text


def _lsp_withdraw(cfg, business_no, object_dst_id, amount):
    payload = {
        "agentId": cfg.get("objectSrcId"),
        "applyAgentId": object_dst_id,
        "accountType": "1",
        "sign": cfg.get("sign"),
        "invoiceType": "0",
        "source": cfg.get("source"),
        "businessNo": business_no,
        "applyAmount": amount,
        "key": cfg.get("key"),
    }
    return _post_json(cfg.get("baseUrl", '') + '/external-api/merchantinfo/v3/submitWithdraw', payload).text


def _lsp_query_order(cfg, business_no):
    payload = {"source": cfg.get("source"), "key": cfg.get("key"), "businessNo": business_no, "sign": cfg.get("sign")}
    return _post_json(cfg.get("baseUrl", '') + '/external-api/behalfPay/transferOrderInfo', payload).text


def _lsp_query_withdraw(cfg, object_dst_id, apply_id):
    payload = {
        "source": cfg.get("source"),
        "key": cfg.get("key"),
        "applyId": apply_id,
        "withdrawAgentNo": object_dst_id,
        "agentId": cfg.get("objectSrcId"),
        "sign": cfg.get("sign"),
    }
    return _post_json(cfg.get("baseUrl", '') + '/external-api/merchantinfo/v3/queryWithdrawState', payload).text


def _check_without_agent(cfg, id_card_no):
    without = cfg.get("withoutAgents", "") or ""
    return id_card_no in without


def lepass_realtime_pay(cfg, rows, params, log):
    """乐商通PLUS / 快乐刷 实时代付（transferMode 区分）"""
    transfer_mode = params.get('transfer_mode') or '7'
    channel_code = params.get('channel_code') or 'lepass'
    success, fail, success_amount = 0, 0, 0
    result_rows = []
    for row in rows:
        id_card_no = _to_str(_cell(row, 5))
        if _check_without_agent(cfg, id_card_no):
            log(f'跳过 身份证{id_card_no} 历史有出款异常')
            result_rows.append(row + ['', '', '历史有出款异常,跳过', '', '', ''])
            continue
        business_no = generate_unique_id(_to_str(_cell(row, 3)))
        bank_card_no = _to_str(_cell(row, 6))
        object_dst_id = _get_sub_agent_id(cfg, bank_card_no, channel_code)
        if not bank_card_no or not object_dst_id:
            result_rows.append(row + ['', '', '需要创建子代理', '', '', ''])
            log(f'流水{_to_str(_cell(row, 3))} 需要创建子代理')
            continue
        amount = _to_int(_cell(row, 8))
        try:
            pay_result = json.loads(_lsp_transfer(cfg, business_no, object_dst_id, amount, transfer_mode))
            if pay_result.get("error_code") == 0 and pay_result.get("data", {}).get("state") == 2:
                order_info = _lsp_query_order(cfg, business_no)
                withdraw_biz_no = business_no + str(amount)
                withdraw_result = json.loads(_lsp_withdraw(cfg, withdraw_biz_no, object_dst_id, amount))
                if withdraw_result.get("error_code") == 0 and withdraw_result.get("error_msg") == "成功":
                    success += 1
                    success_amount += amount
                    apply_id = withdraw_result.get("data", {}).get("applyId")
                    withdraw_query = _lsp_query_withdraw(cfg, object_dst_id, apply_id)
                    result_rows.append(row + [object_dst_id, apply_id, order_info, withdraw_result.get("error_msg"), '', withdraw_query])
                    log(f'{channel_code} 流水{business_no} 代付+提现成功 applyId={apply_id}')
                else:
                    fail += 1
                    result_rows.append(row + [object_dst_id, '', order_info, withdraw_result.get("error_msg"), '', ''])
                    log(f'{channel_code} 流水{business_no} 提现失败: {withdraw_result.get("error_msg")}')
            else:
                fail += 1
                result_rows.append(row + [object_dst_id, '', pay_result.get("error_msg"), '', '', ''])
                log(f'{channel_code} 流水{business_no} 代付失败: {pay_result.get("error_msg")}')
        except Exception as e:
            fail += 1
            result_rows.append(row + [object_dst_id, '', f'异常: {e}', '', '', ''])
            log(f'{channel_code} 流水{business_no} 异常: {e}')
    message = f'代付提现成功：{success}笔, 失败：{fail}笔, 成功金额：{format_amount_to_yuan(success_amount)}元'
    return message, result_rows


def kls_create_pay(cfg, rows, params, log):
    """快乐刷 跑批-创建代付"""
    busi_type = params.get('busi_type') or '144'
    channel_code = params.get('channel_code') or 'kls'
    success, fail, success_amount = 0, 0, 0
    result_rows = []
    for row in rows:
        business_no = generate_unique_id(_to_str(_cell(row, 3)))
        bank_card_no = _to_str(_cell(row, 6))
        object_dst_id = _get_sub_agent_id(cfg, bank_card_no, channel_code)
        if not bank_card_no or not object_dst_id:
            result_rows.append(row + ['', '', '需要创建子代理', '', '', ''])
            continue
        amount = _to_int(_cell(row, 8))
        try:
            pay_result = json.loads(_lsp_create_pay(cfg, business_no, object_dst_id, amount, busi_type))
            if pay_result.get("error_code") == 0:
                success += 1
                success_amount += amount
                req_id = str(pay_result.get("data"))
                result_rows.append(row + [object_dst_id, '', req_id, pay_result.get("error_msg"), '', ''])
                log(f'快乐刷创建代付 流水{business_no} 成功 reqId={req_id}')
            else:
                fail += 1
                result_rows.append(row + [object_dst_id, '', '', pay_result.get("error_msg"), '', ''])
                log(f'快乐刷创建代付 流水{business_no} 失败: {pay_result.get("error_msg")}')
        except Exception as e:
            fail += 1
            result_rows.append(row + [object_dst_id, '', '', f'异常: {e}', '', ''])
            log(f'快乐刷创建代付 流水{business_no} 异常: {e}')
    message = f'快乐刷创建代付成功：{success}笔, 失败：{fail}笔, 成功金额：{format_amount_to_yuan(success_amount)}元'
    return message, result_rows


def kls_query_pay(cfg, rows, params, log):
    """快乐刷 跑批-查询代付"""
    busi_type = params.get('busi_type') or '144'
    success, fail, paying = 0, 0, 0
    result_rows = []
    for row in rows:
        req_id = _to_str(_cell(row, 14))
        if not req_id:
            result_rows.append(row + ['', '', '', '', '创建代付未成功', ''])
            continue
        try:
            pay_result = json.loads(_lsp_query_pay(cfg, req_id, busi_type))
            if pay_result.get("error_code") == 0:
                state = int(pay_result.get("data", {}).get("state"))
                if state == 3:
                    success += 1
                    resp_str = '成功'
                elif state in (2, 4):
                    fail += 1
                    resp_str = '失败'
                else:
                    paying += 1
                    resp_str = f'代付中({state})'
            else:
                fail += 1
                resp_str = pay_result.get("error_msg")
            result_rows.append(row + ['', '', '', '', resp_str, pay_result.get("error_msg")])
            log(f'快乐刷查询代付 reqId={req_id} => {resp_str}')
        except Exception as e:
            fail += 1
            result_rows.append(row + ['', '', '', '', f'异常: {e}', ''])
            log(f'快乐刷查询代付 reqId={req_id} 异常: {e}')
    message = f'快乐刷查询代付 成功：{success}笔, 失败：{fail}笔, 代付中：{paying}笔'
    return message, result_rows


def kls_apply_withdraw(cfg, rows, params, log):
    """快乐刷 跑批-发起提现"""
    channel_code = params.get('channel_code') or 'kls'
    success, fail, success_amount = 0, 0, 0
    result_rows = []
    for row in rows:
        business_no = generate_unique_id(_to_str(_cell(row, 3)))
        amount = _to_int(_cell(row, 8))
        object_dst_id = _to_str(_cell(row, 12))
        try:
            withdraw_result = json.loads(_lsp_withdraw(cfg, business_no, object_dst_id, amount))
            if withdraw_result.get("error_code") == 0 and withdraw_result.get("error_msg") == "成功":
                success += 1
                success_amount += amount
                apply_id = withdraw_result.get("data", {}).get("applyId")
                withdraw_query = _lsp_query_withdraw(cfg, object_dst_id, apply_id)
                result_rows.append(row + [object_dst_id, apply_id, '', withdraw_result.get("error_msg"), '', withdraw_query])
                log(f'快乐刷发起提现 流水{business_no} 成功 applyId={apply_id}')
            else:
                fail += 1
                result_rows.append(row + [object_dst_id, '', '', withdraw_result.get("error_msg"), '', ''])
                log(f'快乐刷发起提现 流水{business_no} 失败: {withdraw_result.get("error_msg")}')
        except Exception as e:
            fail += 1
            result_rows.append(row + [object_dst_id, '', '', f'异常: {e}', '', ''])
            log(f'快乐刷发起提现 流水{business_no} 异常: {e}')
    message = f'快乐刷发起提现成功：{success}笔, 失败：{fail}笔, 成功金额：{format_amount_to_yuan(success_amount)}元'
    return message, result_rows


def lsp_withdraw_query(cfg, rows, params, log):
    """乐商通PLUS / 快乐刷 提现状态查询（按 applyId）"""
    success, fail, paying = 0, 0, 0
    result_rows = []
    for row in rows:
        object_dst_id = _to_str(_cell(row, 12))
        apply_id = _to_str(_cell(row, 13))
        if not apply_id:
            result_rows.append(row + ['', '', '', '', '', '无applyId'])
            continue
        try:
            result = json.loads(_lsp_query_withdraw(cfg, object_dst_id, apply_id))
            if result.get("error_code") == 0:
                f_state = result.get("data", {}).get("F_state")
                if f_state in (-1, "6", 6):
                    paying += 1
                    resp_str = '打款中'
                elif f_state == "9":
                    success += 1
                    resp_str = '成功'
                else:
                    fail += 1
                    resp_str = f'失败({f_state})'
            else:
                fail += 1
                resp_str = result.get("error_msg")
            result_rows.append(row + ['', '', '', '', '', resp_str])
            log(f'提现查询 applyId={apply_id} => {resp_str}')
        except Exception as e:
            fail += 1
            result_rows.append(row + ['', '', '', '', '', f'异常: {e}'])
            log(f'提现查询 applyId={apply_id} 异常: {e}')
    message = f'打款成功：{success}笔, 失败：{fail}笔, 打款中：{paying}笔'
    return message, result_rows


# ---------------------------------------------------------------------------
# 统一入口
# ---------------------------------------------------------------------------

def execute_pay(channel, cfg, rows, params, log):
    """根据渠道 + 接口类型 + 跑批步骤分发执行，返回 (message, result_rows)"""
    interface_type = params.get('interface_type', '代付')
    real_time = params.get('real_time', '是')
    execute_type = params.get('execute_type', '创建代付')

    if channel == 'helipay':
        return helipay_pay(cfg, rows, params, log)
    elif channel == 'dianyin':
        if interface_type == '查询':
            return dianyin_query_batch(cfg, rows, params, log)
        return dianyin_pay(cfg, rows, params, log)
    elif channel in ('lepass', 'kls'):
        if interface_type == '查询':
            return lsp_withdraw_query(cfg, rows, params, log)
        # 代付
        if channel == 'lepass':
            return lepass_realtime_pay(cfg, rows, params, log)
        # 快乐刷
        if real_time == '是':
            return lepass_realtime_pay(cfg, rows, params, log)
        # 跑批
        if execute_type == '创建代付':
            return kls_create_pay(cfg, rows, params, log)
        elif execute_type == '查询代付':
            return kls_query_pay(cfg, rows, params, log)
        else:
            return kls_apply_withdraw(cfg, rows, params, log)
    else:
        raise ValueError(f'未知渠道: {channel}')
