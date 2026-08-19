import argparse
import json
import os
import sys
import subprocess
from pathlib import Path


def _bootstrap_venv():
    mark = os.environ.get("VENV_BOOTSTRAPPED")
    if mark == "1":
        return

    script_dir = Path(__file__).resolve().parent
    scripts_dir = script_dir.parent
    venv_dir = scripts_dir / ".venv"
    req_file = script_dir / "requirements.txt"

    if sys.platform == "win32":
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python = venv_dir / "bin" / "python"

    need_install = False
    if not venv_python.exists():
        print("[bootstrap] 创建虚拟环境:", venv_dir)
        subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])
        need_install = True

    if not venv_python.exists():
        print("[bootstrap] 错误：虚拟环境 Python 未找到:", venv_python)
        sys.exit(1)

    if req_file.exists():
        print("[bootstrap] 检查并安装依赖 (requirements.txt)...")
        result = subprocess.run(
            [
                str(venv_python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "-r",
                str(req_file),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print("[bootstrap] 依赖安装失败:")
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
            sys.exit(1)
        if need_install or result.stdout.strip():
            print("[bootstrap] 依赖检查/安装完成")
    else:
        print("[bootstrap] 警告: 未找到 requirements.txt:", req_file)

    print("[bootstrap] 使用虚拟环境重新执行脚本...")
    env = os.environ.copy()
    env["VENV_BOOTSTRAPPED"] = "1"
    sys.exit(
        subprocess.call(
            [str(venv_python), str(Path(__file__).resolve())] + sys.argv[1:],
            env=env,
        )
    )


_bootstrap_venv()

import zfUtils


def parse_args():
    parser = argparse.ArgumentParser(description="中付设备绑定脚本")
    parser.add_argument("--merchant_id", required=True, help="商户ID（同时用作 channel_merchant_no 和 data_json.merchantId）")
    parser.add_argument("--terminal_id", required=True, help="终端ID（data_json.terminalId）")
    parser.add_argument("--device_sn", required=True, help="设备序列号（data_json.deviceSN）")
    parser.add_argument("--merchant_no", required=True, help="商户编号（merchant_no）")
    parser.add_argument("--channel", default="zf", choices=["zf", "zf_rj"], help="渠道类型，默认 zf")
    parser.add_argument("--method", default="bindDevice", help="接口方法，默认 bindDevice")
    parser.add_argument("--remark", default="中付A模式绑定", help="备注")
    return parser.parse_args()


def main():
    args = parse_args()

    zf_util = zfUtils.ZfUtil("https://tyuen-partner-gateway.qtopay.cn:8858/app-tyuen-partner-gateway/api")

    channel_info = {
        "zf_rj": {
            "appId": "juHeBa",
            "zfSm2Pub": "FE748C14FE884DB1EA855A4FCC635B59F076D972FE2AA4A4C60FCE0E97905F988AF4282B956D0736597B4B261A902691563BBA03C5D67994D4966F5DF9C2AD31",
            "jhbSm2Pri": "46B0AFA674059A3F571D69EA09997233B17282F852458C9C44AB41706AF77923"
        },
        "zf": {
            "appId": "zhangYin",
            "zfSm2Pub": "4D295C08EA4BE677C251C1D67E425581FE404D446D67B7DE10B6F6BB33DC358BE5EC009E19A53D0744E0BC9D7E3DE504140C29C30160AD8FEEF1336AE8D4DA4D",
            "jhbSm2Pri": "3EC4539E2CE2F565F21530357FAFB498529D7E7F7048EF942AB80FA50E4D1E72"
        }
    }

    data_json = json.dumps({
        "merchantId": args.merchant_id,
        "terminalId": args.terminal_id,
        "deviceSN": args.device_sn
    }, ensure_ascii=False)

    try:
        response = zf_util.post(
            data_json=data_json,
            channel_info=channel_info[args.channel],
            method=args.method,
            merchant_no=args.merchant_no,
            channel_merchant_no=args.merchant_id,
            remark=args.remark
        )
        print("响应结果:", response)
    except Exception as e:
        print("请求失败:", str(e))


if __name__ == "__main__":
    main()