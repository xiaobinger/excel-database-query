import json
import requests
from datetime import datetime
from gmssl import sm2, sm3, func
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ZfUtil:
    def __init__(self, host):
        """
        初始化中付工具类
        :param host: 请求地址
        """
        self.host = host

    def post(self, data_json, channel_info, method, merchant_no, channel_merchant_no, remark, clazz=None, request_id=None):
        """
        中付POST请求方法
        
        :param data_json: 请求数据JSON字符串
        :param channel_info: 包含appId, zfSm2Pub, jhbSm2Pri的字典
        :param method: 请求方法名
        :param merchant_no: 商户号
        :param channel_merchant_no: 通道商户号
        :param remark: 备注信息
        :param clazz: 响应数据类型(可选)
        :param request_id: 请求ID(可选)
        :return: 响应对象
        """
        # 打印请求日志
        if method != "fileUpload":
            logger.info(f"中付-{remark}-发起请求，商户号：{merchant_no}，通道商户号：{channel_merchant_no}，方法名：{method}，请求参数:{data_json}")
        else:
            # 文件上传接口特殊处理
            data_dict = json.loads(data_json)
            data_dict["buffer"] = "略"
            logger.info(f"中付-{remark}-发起请求，商户号：{merchant_no}，通道商户号：{channel_merchant_no}，方法名：{method}，请求参数:{json.dumps(data_dict)}")

        app_id = channel_info.get("appId")
        zf_sm2_pub = channel_info.get("zfSm2Pub")
        jhb_sm2_pri = channel_info.get("jhbSm2Pri")

        try:
            # 1. SM2加密
            get_encrypt_param = {
                "data":data_json,
                "publicKey":zf_sm2_pub
            }
            D = requests.post(
                "http://192.168.10.203:8082/test/getZfEncrypt",
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                data=json.dumps(get_encrypt_param)
            )
            logger.info(f"中付-{remark}-加密结果，商户号：{merchant_no}，加密结果：{D.text}")
            
            # 2. 加签
            M = f"appId={app_id}&method={method}&data={D.text}"
            get_sign_param = {
                "data":M,
                "privateKey":jhb_sm2_pri
            }
            S = requests.post(
                "http://192.168.10.203:8082/test/getZfSign",
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                data=json.dumps(get_sign_param)
            )
            logger.info(f"中付-{remark}-加签结果，商户号：{merchant_no}，加签结果：{S.text}")
            # 组装请求参数
            base_request = {
                "appId": app_id,
                "method": method,
                "requestId": request_id or datetime.now().strftime("%Y%m%d%H%M%S%f"),
                "requestTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "version": "1.0",
                "data": D.text,
                "sign": S.text
            }
            
            # 发送请求
            response = requests.post(
                self.host,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                data=json.dumps(base_request)
            )
            response.raise_for_status()
            
            # 处理响应
            body = response.json()
            logger.info(f"中付-{remark}-响应，商户号：{merchant_no}，响应body：{json.dumps(body)}")
            
            if body.get("respCode") == "0000":  # 假设000000表示成功
                # 验签
                resp_param = f"respCode={body.get('respCode')}"
                if body.get("data"):
                    resp_param += f"&data={body.get('data')}"
                
                verify = self._sm2_verify(resp_param, body.get("sign"), zf_sm2_pub)
                if not verify:
                    raise RuntimeError("验签失败")
                
                # 解密
                if body.get("data") and clazz:
                    try:
                        decrypted_data = self._sm2_decrypt(body.get("data"), jhb_sm2_pri)
                        logger.info(f"中付-{remark}-解密数据，商户号：{merchant_no}，data明文：{decrypted_data}")
                        
                        # 如果需要返回特定类型的对象，可以在这里处理
                        # t = json.loads(decrypted_data)  # 转换为Python对象
                        # base_response["t"] = t
                    except Exception as e:
                        logger.error(f"解密失败: {str(e)}")
                        raise
                
                return body  # 返回完整响应，或根据需要构造特定对象
            else:
                raise RuntimeError(f"系统繁忙，请稍后再试[ERR_ZF0119]: {body.get('respMsg')}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"中付-{remark}-响应，商户号：{merchant_no}，响应状态码：{response.status_code if 'response' in locals() else '未知'}，错误：{str(e)}")
            raise RuntimeError(f"系统繁忙，请稍后再试[ERR_ZF0119]: {str(e)}")
        except Exception as e:
            logger.error(f"中付-{remark}-请求处理失败: {str(e)}")
            raise

    def _sm2_encrypt(self, data, public_key):
        """
        SM2加密
        :param data: 要加密的数据
        :param public_key: SM2公钥(16进制字符串)
        :return: 加密后的16进制字符串
        """
        try:
            # 直接使用公钥字符串，gmssl库期望字符串格式
            # 确保公钥包含04前缀
            if not public_key.startswith('04'):
                public_key = '04' + public_key
            
            # 创建SM2实例
            sm2_crypt = sm2.CryptSM2(
                public_key=public_key,
                private_key=None,
                mode=1
            )
            
            # 加密(使用随机数)
            encrypt_data = sm2_crypt.encrypt(data.encode('utf-8'))
            return encrypt_data.hex()
        except Exception as e:
            logger.error(f"SM2加密失败: {str(e)}")
            raise

    def _sm2_decrypt(self, data, private_key):
        """
        SM2解密
        :param data: 要解密的16进制字符串
        :param private_key: SM2私钥(16进制字符串)
        :return: 解密后的字符串
        """
        try:
            # 直接使用私钥字符串，gmssl库期望字符串格式
            # 确保私钥长度为偶数
            if len(private_key) % 2 != 0:
                private_key = '0' + private_key
            
            # 创建SM2实例，使用正确的公钥
            # 注意：解密时需要使用与加密相同的公钥
            public_key = "04C88554D3CA8FA03AD94957F245507894D713CBB1055798A6F6211E1BF9288D1B98E27B3041CF7EBB456B736E916EC4391309E8ED88AA36907679C76EBF44ACFC"
            sm2_crypt = sm2.CryptSM2(
                public_key=public_key,
                private_key=private_key,
                mode=1
            )
            
            # 解密
            decrypt_data = sm2_crypt.decrypt(bytes.fromhex(data))
            return decrypt_data.decode('utf-8')
        except Exception as e:
            logger.error(f"SM2解密失败: {str(e)}")
            raise

    def _sm2_sign(self, data, private_key):
        """
        SM2签名
        :param data: 要签名的数据
        :param private_key: SM2私钥(16进制字符串)
        :return: 签名的16进制字符串
        """
        try:
            # 直接使用私钥字符串，gmssl库期望字符串格式
            # 确保私钥长度为偶数
            if len(private_key) % 2 != 0:
                private_key = '0' + private_key
                logger.info(f"修正后的私钥: {private_key[:16]}...")
            
            # 创建SM2实例，使用与私钥匹配的公钥
            # 注意：在SM2签名中，公钥用于生成SM3的Z值，需要与私钥匹配
            # 这里我们使用core/security.py中的方法，直接使用sign_with_sm3签名
            # 导入security模块中的add_sign方法
            from core.security import add_sign
            # 使用key_id为默认值
            signature = add_sign(data, private_key, "31323334353637383132333435363738")
            return signature
        except Exception as e:
            logger.error(f"SM2签名失败: {str(e)}")
            raise

    def _sm2_verify(self, data, sign, public_key):
        """
        SM2验签
        :param data: 原始数据
        :param sign: 签名(16进制字符串)
        :param public_key: SM2公钥(16进制字符串)
        :return: 验签结果(True/False)
        """
        try:
            # 直接使用公钥字符串，gmssl库期望字符串格式
            # 确保公钥包含04前缀
            if not public_key.startswith('04'):
                public_key = '04' + public_key
            
            # 创建SM2实例
            sm2_crypt = sm2.CryptSM2(
                public_key=public_key,
                private_key=None,
                mode=1
            )
            
            # 注意：sign是字符串格式，verify_with_sm3方法需要字符串格式的签名
            # 不需要转换为bytes，直接使用字符串签名进行验签
            return sm2_crypt.verify_with_sm3(sign, data.encode('utf-8'))
        except Exception as e:
            logger.error(f"SM2验签失败: {str(e)}")
            raise