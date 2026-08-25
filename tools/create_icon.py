from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "qingliu.ico"
PREVIEW = ROOT / "assets" / "qingliu.png"


def main() -> None:
    size = 256
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((12, 12, 244, 244), radius=54, fill="#0F766E")

    # 白色水滴代表“清流”，内部柱形表示账单分析。
    draw.polygon([(128, 39), (72, 126), (184, 126)], fill="#F8FAFC")
    draw.ellipse((72, 86, 184, 202), fill="#F8FAFC")
    draw.rectangle((98, 142, 111, 174), fill="#0F766E")
    draw.rectangle((122, 126, 135, 174), fill="#0F766E")
    draw.rectangle((146, 108, 159, 174), fill="#0F766E")
    draw.rounded_rectangle((92, 177, 165, 184), radius=3, fill="#0F766E")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(PREVIEW, format="PNG")
    image.save(OUTPUT, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(OUTPUT)


if __name__ == "__main__":
    main()
