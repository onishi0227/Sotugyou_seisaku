
from pathlib import Path

import qrcode


# PCのWi-Fi側のIPv4アドレス
PC_IP = "10.250.157.177"

# 店舗ID
STORE_ID = 1

# テーブル数
TABLE_COUNT = 10

# QRコードの保存先
output_dir = Path(__file__).parent / "qr_codes"
output_dir.mkdir(exist_ok=True)

# テーブル1〜10のQRコードを作成
for table_no in range(1, TABLE_COUNT + 1):
    url = f"http://{PC_IP}:8000/order/{STORE_ID}/{table_no}"

    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=4,
    )

    qr.add_data(url)
    qr.make(fit=True)

    image = qr.make_image(
        fill_color="black",
        back_color="white",
    )

    output_path = (
        output_dir
        / f"qr_store_{STORE_ID}_table_{table_no}.png"
    )

    image.save(output_path)

    print(f"テーブル{table_no}のQRコードを作成しました。")
    print(f"保存先: {output_path}")
    print(f"アクセス先: {url}")
    print("-" * 40)

print("全10卓のQRコード作成が完了しました。")
