"""
画像処理ヘルパースクリプト
Twitter DM送信用の画像を準備するためのユーティリティ
"""

from PIL import Image
import os
from pathlib import Path
import json


class ImageHelper:
    """画像処理のヘルパークラス"""

    @staticmethod
    def resize_image(input_path: str, output_path: str = None, max_size_mb: float = 5.0):
        """
        画像をリサイズして5MB以下にする

        Args:
            input_path: 入力画像のパス
            output_path: 出力画像のパス（Noneの場合は同じディレクトリに_resized追加）
            max_size_mb: 最大ファイルサイズ（MB）
        """
        if not output_path:
            path = Path(input_path)
            output_path = path.parent / f"{path.stem}_resized{path.suffix}"

        img = Image.open(input_path)

        # 現在のファイルサイズを確認
        current_size_mb = os.path.getsize(input_path) / (1024 * 1024)

        if current_size_mb <= max_size_mb:
            print(f"画像はすでに{max_size_mb}MB以下です: {current_size_mb:.2f}MB")
            return

        # 段階的にサイズを縮小
        quality = 95
        scale = 1.0

        while current_size_mb > max_size_mb and quality > 20:
            # スケールを調整
            if current_size_mb > max_size_mb * 2:
                scale *= 0.7
            else:
                scale *= 0.9

            # リサイズ
            new_size = (int(img.width * scale), int(img.height * scale))
            resized = img.resize(new_size, Image.Resampling.LANCZOS)

            # 保存（一時的に）
            resized.save(output_path, quality=quality, optimize=True)

            # サイズを確認
            current_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"リサイズ中... サイズ: {new_size}, ファイルサイズ: {current_size_mb:.2f}MB")

            # 品質を下げる
            quality -= 5

        print(f"リサイズ完了: {output_path} ({current_size_mb:.2f}MB)")

    @staticmethod
    def batch_resize_images(directory: str, max_size_mb: float = 5.0):
        """
        ディレクトリ内のすべての画像をリサイズ

        Args:
            directory: 画像ディレクトリ
            max_size_mb: 最大ファイルサイズ（MB）
        """
        supported_formats = ['.jpg', '.jpeg', '.png', '.gif', '.webp']

        for file_path in Path(directory).iterdir():
            if file_path.suffix.lower() in supported_formats:
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

                if file_size_mb > max_size_mb:
                    print(f"\nリサイズ対象: {file_path.name} ({file_size_mb:.2f}MB)")
                    ImageHelper.resize_image(str(file_path))

    @staticmethod
    def convert_to_jpg(input_path: str, output_path: str = None, quality: int = 85):
        """
        画像をJPG形式に変換

        Args:
            input_path: 入力画像のパス
            output_path: 出力画像のパス
            quality: JPG品質（1-100）
        """
        if not output_path:
            path = Path(input_path)
            output_path = path.parent / f"{path.stem}.jpg"

        img = Image.open(input_path)

        # RGBモードに変換（JPGはアルファチャンネルをサポートしない）
        if img.mode in ('RGBA', 'LA', 'P'):
            # 白背景を作成
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # 保存
        img.save(output_path, 'JPEG', quality=quality, optimize=True)
        print(f"JPGに変換: {output_path}")

    @staticmethod
    def create_thumbnail(input_path: str, output_path: str = None, size: tuple = (800, 600)):
        """
        サムネイルを作成

        Args:
            input_path: 入力画像のパス
            output_path: 出力画像のパス
            size: サムネイルサイズ (width, height)
        """
        if not output_path:
            path = Path(input_path)
            output_path = path.parent / f"{path.stem}_thumb{path.suffix}"

        img = Image.open(input_path)
        img.thumbnail(size, Image.Resampling.LANCZOS)
        img.save(output_path, optimize=True)
        print(f"サムネイル作成: {output_path}")

    @staticmethod
    def validate_images_in_config(config_file: str = 'config.json', images_dir: str = 'images'):
        """
        config.jsonで指定された画像ファイルの存在を確認

        Args:
            config_file: 設定ファイルのパス
            images_dir: 画像ディレクトリ
        """
        print(f"\n画像ファイルの検証を開始...\n")

        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        missing_images = []
        found_images = []

        # メッセージテンプレートの画像を確認
        templates = config.get('message_templates', {})
        for category, messages in templates.items():
            for msg in messages:
                if isinstance(msg, dict) and msg.get('image'):
                    image_name = msg['image']
                    image_path = os.path.join(images_dir, image_name)

                    if os.path.exists(image_path):
                        size_mb = os.path.getsize(image_path) / (1024 * 1024)
                        found_images.append((category, image_name, size_mb))
                        print(f"✓ {category}/{image_name} ({size_mb:.2f}MB)")
                    else:
                        missing_images.append((category, image_name))
                        print(f"✗ {category}/{image_name} - ファイルが見つかりません")

        # カスタムメッセージの画像を確認
        for recipient in config.get('recipients', []):
            if recipient.get('custom_messages'):
                username = recipient.get('username', 'Unknown')
                for msg in recipient['custom_messages']:
                    if isinstance(msg, dict) and msg.get('image'):
                        image_name = msg['image']
                        image_path = os.path.join(images_dir, image_name)

                        if os.path.exists(image_path):
                            size_mb = os.path.getsize(image_path) / (1024 * 1024)
                            found_images.append((f"user:{username}", image_name, size_mb))
                            print(f"✓ user:{username}/{image_name} ({size_mb:.2f}MB)")
                        else:
                            missing_images.append((f"user:{username}", image_name))
                            print(f"✗ user:{username}/{image_name} - ファイルが見つかりません")

        # サマリー
        print(f"\n=== 検証結果 ===")
        print(f"見つかった画像: {len(found_images)}個")
        print(f"見つからない画像: {len(missing_images)}個")

        # 5MB以上の画像を警告
        large_images = [(cat, name, size) for cat, name, size in found_images if size > 5.0]
        if large_images:
            print(f"\n⚠ 5MB以上の画像（リサイズ推奨）:")
            for cat, name, size in large_images:
                print(f"  - {cat}/{name}: {size:.2f}MB")

        return len(missing_images) == 0


def main():
    """メイン関数"""
    print("=" * 50)
    print("Twitter DM 画像処理ヘルパー")
    print("=" * 50)

    while True:
        print("\n操作を選択してください:")
        print("1. config.jsonの画像ファイルを検証")
        print("2. 画像をリサイズ（5MB以下に）")
        print("3. ディレクトリ内の画像を一括リサイズ")
        print("4. 画像をJPGに変換")
        print("5. サムネイルを作成")
        print("0. 終了")

        choice = input("\n選択 (0-5): ").strip()

        if choice == '0':
            break
        elif choice == '1':
            ImageHelper.validate_images_in_config()
        elif choice == '2':
            path = input("画像ファイルのパス: ").strip()
            if os.path.exists(path):
                ImageHelper.resize_image(path)
            else:
                print("ファイルが見つかりません")
        elif choice == '3':
            directory = input("画像ディレクトリのパス (デフォルト: images): ").strip() or 'images'
            if os.path.exists(directory):
                ImageHelper.batch_resize_images(directory)
            else:
                print("ディレクトリが見つかりません")
        elif choice == '4':
            path = input("画像ファイルのパス: ").strip()
            if os.path.exists(path):
                ImageHelper.convert_to_jpg(path)
            else:
                print("ファイルが見つかりません")
        elif choice == '5':
            path = input("画像ファイルのパス: ").strip()
            if os.path.exists(path):
                ImageHelper.create_thumbnail(path)
            else:
                print("ファイルが見つかりません")
        else:
            print("無効な選択です")


if __name__ == "__main__":
    # Pillowのインストール確認
    try:
        import PIL
    except ImportError:
        print("Pillowライブラリが必要です。")
        print("インストール: pip install Pillow")
        exit(1)

    main()