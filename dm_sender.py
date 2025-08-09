import tweepy
import google.generativeai as genai
import json
import time
import schedule
import logging
from datetime import datetime
from typing import List, Dict
import random
import os
from pathlib import Path
import shutil

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('dm_sender.log'),
        logging.StreamHandler()
    ]
)


class DMSender:
    def __init__(self, config_file: str = 'config.json'):
        """
        DMSenderクラスの初期化

        Args:
            config_file (str): 設定ファイルのパス
        """
        self.config = self.load_config(config_file)
        self.twitter_api = self.setup_twitter_api()
        self.setup_gemini()

    def load_config(self, config_file: str) -> Dict:
        """設定ファイルを読み込む（必要に応じて自動生成）"""
        try:
            # config.jsonが存在しない場合、config-example.jsonから生成
            if not os.path.exists(config_file):
                self.create_config_from_example(config_file)

            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # 設定の検証
            self.validate_config(config)
            logging.info("設定ファイルを正常に読み込みました")
            return config

        except FileNotFoundError:
            logging.error(f"設定ファイル {config_file} が見つかりません")
            raise
        except json.JSONDecodeError:
            logging.error("設定ファイルのJSON形式が正しくありません")
            raise

    def create_config_from_example(self, config_file: str):
        """config-example.jsonからconfig.jsonを生成"""
        example_file = 'config-example.json'

        if not os.path.exists(example_file):
            logging.error(f"テンプレートファイル {example_file} が見つかりません")
            raise FileNotFoundError(f"テンプレートファイル {example_file} が必要です")

        try:
            shutil.copy2(example_file, config_file)
            logging.info(f"{example_file} から {config_file} を生成しました")

            print("=" * 60)
            print("🔧 初回セットアップが必要です")
            print("=" * 60)
            print(f"📋 {config_file} が生成されました")
            print("📝 以下の設定を編集してください：")
            print()
            print("1. Twitter API認証情報:")
            print("   - consumer_key")
            print("   - consumer_secret")
            print("   - access_token")
            print("   - access_token_secret")
            print()
            print("2. Google Gemini API認証情報:")
            print("   - api_key")
            print()
            print("3. 送信先ユーザー情報:")
            print("   - target_users の user_id を実際の値に変更")
            print()
            print("4. 画像フォルダ:")
            print("   - ./images フォルダに送信したい画像を配置")
            print()
            print("⚠️  設定完了後、プログラムを再実行してください")
            print("=" * 60)

            # プログラムを一時停止
            input("設定完了後、Enterキーを押してください...")

        except Exception as e:
            logging.error(f"設定ファイル生成エラー: {e}")
            raise

    def validate_config(self, config: Dict):
        """設定ファイルの内容を検証"""
        required_sections = ['twitter', 'gemini', 'target_users']
        missing_sections = []

        for section in required_sections:
            if section not in config:
                missing_sections.append(section)

        if missing_sections:
            raise ValueError(f"設定ファイルに必要なセクションがありません: {missing_sections}")

        # Twitter API設定の検証
        twitter_keys = ['consumer_key', 'consumer_secret', 'access_token', 'access_token_secret']
        for key in twitter_keys:
            if not config['twitter'].get(key) or config['twitter'][key].startswith('YOUR_'):
                logging.warning(f"Twitter API設定が未完了です: {key}")

        # Gemini API設定の検証
        if not config['gemini'].get('api_key') or config['gemini']['api_key'].startswith('YOUR_'):
            logging.warning("Gemini API設定が未完了です: api_key")

        # 送信先ユーザーの検証
        if not config['target_users']:
            logging.warning("送信先ユーザーが設定されていません")
        else:
            for user in config['target_users']:
                if not user.get('user_id') or user['user_id'] in ['123456789', '987654321']:
                    logging.warning(f"サンプルのユーザーIDが残っています: {user.get('username', 'Unknown')}")

        # 画像フォルダの確認
        image_settings = config.get('image_settings', {})
        if image_settings.get('enabled'):
            folder_path = image_settings.get('folder_path', './images')
            if not os.path.exists(folder_path):
                logging.warning(f"画像フォルダが存在しません: {folder_path}")
                try:
                    os.makedirs(folder_path)
                    logging.info(f"画像フォルダを作成しました: {folder_path}")
                except Exception as e:
                    logging.error(f"画像フォルダの作成に失敗: {e}")

        logging.info("設定ファイルの検証が完了しました")

    def setup_twitter_api(self) -> tweepy.API:
        """Twitter APIの設定"""
        try:
            twitter_config = self.config['twitter']

            # Twitter API v1.1用の認証
            auth = tweepy.OAuth1UserHandler(
                consumer_key=twitter_config['consumer_key'],
                consumer_secret=twitter_config['consumer_secret'],
                access_token=twitter_config['access_token'],
                access_token_secret=twitter_config['access_token_secret']
            )

            api = tweepy.API(auth, wait_on_rate_limit=True)

            # 認証テスト
            api.verify_credentials()
            logging.info("Twitter API認証が成功しました")
            return api

        except Exception as e:
            logging.error(f"Twitter API設定エラー: {e}")
            raise

    def setup_gemini(self):
        """Google Gemini APIの設定"""
        try:
            genai.configure(api_key=self.config['gemini']['api_key'])
            self.gemini_model = genai.GenerativeModel(
                model_name=self.config['gemini'].get('model', 'gemini-2.5-flash')
            )
            logging.info("Google Gemini API設定が完了しました")
        except Exception as e:
            logging.error(f"Gemini API設定エラー: {e}")
            raise

    def generate_message(self) -> str:
        """Geminiを使ってメッセージを生成"""
        try:
            prompts = self.config['message_prompts']
            selected_prompt = random.choice(prompts)

            response = self.gemini_model.generate_content(selected_prompt)
            message = response.text.strip()

            # メッセージの長さ制限（DMは10,000文字まで）
            if len(message) > 9500:
                message = message[:9500] + "..."

            logging.info(f"メッセージを生成しました: {message[:50]}...")
            return message

        except Exception as e:
            logging.error(f"メッセージ生成エラー: {e}")
            # フォールバックメッセージ
            fallback_messages = self.config.get('fallback_messages', [
                "このメッセージは表示されないはずだよ。https://github.com/coffin399/im64DMSender"
            ])
            return random.choice(fallback_messages)

    def get_random_image(self) -> str:
        """設定されたフォルダからランダムに画像を選択"""
        try:
            image_folder = self.config.get('image_settings', {}).get('folder_path')
            if not image_folder:
                return None

            image_folder_path = Path(image_folder)
            if not image_folder_path.exists():
                logging.warning(f"画像フォルダが存在しません: {image_folder}")
                return None

            # サポートする画像形式
            supported_formats = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

            # フォルダ内の画像ファイルを取得
            image_files = [
                f for f in image_folder_path.iterdir()
                if f.is_file() and f.suffix.lower() in supported_formats
            ]

            if not image_files:
                logging.warning(f"画像フォルダに対応ファイルがありません: {image_folder}")
                return None

            selected_image = random.choice(image_files)
            logging.info(f"選択された画像: {selected_image.name}")
            return str(selected_image)

        except Exception as e:
            logging.error(f"画像選択エラー: {e}")
            return None

    def upload_media(self, image_path: str) -> str:
        """画像をTwitterにアップロードしてmedia_idを取得"""
        try:
            # ファイルサイズチェック（5MB制限）
            file_size = os.path.getsize(image_path)
            if file_size > 5 * 1024 * 1024:  # 5MB
                logging.warning(f"画像ファイルが大きすぎます: {file_size} bytes")
                return None

            # Twitter API v1.1を使用してメディアアップロード
            media = self.twitter_api.media_upload(image_path)
            logging.info(f"画像アップロード完了: media_id={media.media_id}")
            return media.media_id

        except Exception as e:
            logging.error(f"画像アップロードエラー: {e}")
            return None

    def send_dm_to_user(self, user_id: str, message: str, media_id: str = None) -> bool:
        """指定されたユーザーにDMを送信（画像付きオプション）"""
        try:
            # Twitter API v2を使用してDM送信
            client = tweepy.Client(
                consumer_key=self.config['twitter']['consumer_key'],
                consumer_secret=self.config['twitter']['consumer_secret'],
                access_token=self.config['twitter']['access_token'],
                access_token_secret=self.config['twitter']['access_token_secret']
            )

            # メディア付きDMの場合
            if media_id:
                response = client.create_direct_message(
                    dm_conversation_id=user_id,
                    text=message,
                    media_id=media_id
                )
                logging.info(f"ユーザーID {user_id} に画像付きDMを送信しました")
            else:
                response = client.create_direct_message(
                    dm_conversation_id=user_id,
                    text=message
                )
                logging.info(f"ユーザーID {user_id} にテキストDMを送信しました")

            return True

        except tweepy.TooManyRequests:
            logging.warning("レート制限に達しました。しばらく待機します...")
            time.sleep(900)  # 15分待機
            return False
        except tweepy.Forbidden:
            logging.error(f"ユーザーID {user_id} への送信が拒否されました（ブロックまたはDM無効）")
            return False
        except Exception as e:
            logging.error(f"DM送信エラー: {e}")
            return False

    def send_messages_to_all(self):
        """全ての対象ユーザーにメッセージを送信"""
        target_users = self.config['target_users']

        logging.info(f"={datetime.now().strftime('%Y-%m-%d %H:%M:%S')} DM送信開始 =")
        logging.info(f"対象ユーザー数: {len(target_users)}")

        # 画像送信設定の確認
        image_enabled = self.config.get('image_settings', {}).get('enabled', False)
        send_probability = self.config.get('image_settings', {}).get('send_probability', 0.5)

        success_count = 0

        for user_info in target_users:
            user_id = user_info.get('user_id')
            username = user_info.get('username', 'Unknown')

            if not user_id:
                logging.warning(f"ユーザーID が指定されていません: {user_info}")
                continue

            # メッセージ生成
            message = self.generate_message()

            # 画像送信の判定
            media_id = None
            if image_enabled and random.random() < send_probability:
                image_path = self.get_random_image()
                if image_path:
                    media_id = self.upload_media(image_path)
                    if media_id:
                        logging.info(f"画像付きDMを準備: {Path(image_path).name}")
                    else:
                        logging.warning("画像アップロードに失敗、テキストのみで送信します")

            # DM送信
            if self.send_dm_to_user(user_id, message, media_id):
                success_count += 1
                if media_id:
                    logging.info(f"✓ {username} (ID: {user_id}) に画像付きDM送信完了")
                else:
                    logging.info(f"✓ {username} (ID: {user_id}) にテキストDM送信完了")
            else:
                logging.warning(f"✗ {username} (ID: {user_id}) への送信失敗")

            # API制限を考慮して少し待機
            time.sleep(3)  # 画像処理を考慮して少し長めに

        logging.info(f"DM送信完了: {success_count}/{len(target_users)} 件成功")
        logging.info("=" * 50)

    def start_scheduler(self):
        """スケジューラーを開始"""
        # 4時間ごとに実行
        schedule.every(4).hours.do(self.send_messages_to_all)

        logging.info("DM送信スケジューラーを開始しました（4時間ごと）")
        logging.info("プログラムを停止するにはCtrl+Cを押してください")

        # 最初の実行
        self.send_messages_to_all()

        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # 1分ごとにスケジュールをチェック
        except KeyboardInterrupt:
            logging.info("プログラムが停止されました")


def main():
    """メイン関数"""
    try:
        sender = DMSender()
        sender.start_scheduler()
    except Exception as e:
        logging.error(f"プログラム実行エラー: {e}")


if __name__ == "__main__":
    main()