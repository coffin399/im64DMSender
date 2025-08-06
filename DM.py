import tweepy
import schedule
import time
import logging
from datetime import datetime
from typing import List, Dict, Optional, Union
import json
import os
import random
from pathlib import Path

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('twitter_dm_log.txt'),
        logging.StreamHandler()
    ]
)


class TwitterDMScheduler:
    """Twitter DMを定期的に送信するクラス"""

    def __init__(self, config_file='config.json'):
        """
        初期化

        Args:
            config_file: 設定ファイルのパス
        """
        self.config = self.load_config(config_file)
        self.api = self.authenticate()
        self.client = self.authenticate_v2()

    def load_config(self, config_file: str) -> Dict:
        """
        設定ファイルを読み込む

        Args:
            config_file: 設定ファイルのパス

        Returns:
            設定情報の辞書
        """
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # 設定ファイルのテンプレートを作成
            template = {
                "api_credentials": {
                    "api_key": "YOUR_API_KEY",
                    "api_secret": "YOUR_API_SECRET",
                    "access_token": "YOUR_ACCESS_TOKEN",
                    "access_token_secret": "YOUR_ACCESS_TOKEN_SECRET",
                    "bearer_token": "YOUR_BEARER_TOKEN"
                },
                "schedule_settings": {
                    "interval_hours": 6,
                    "enable_timestamp": True,
                    "randomize_messages": False
                },
                "media_settings": {
                    "images_directory": "images",
                    "max_image_size_mb": 5,
                    "supported_formats": ["jpg", "jpeg", "png", "gif", "webp"]
                },
                "message_templates": {
                    "greeting": [
                        {
                            "text": "おはようございます！今日も素晴らしい一日になりますように。",
                            "image": "morning.jpg"
                        },
                        {
                            "text": "こんにちは！お元気ですか？",
                            "image": null
                        }
                    ],
                    "reminder": [
                        {
                            "text": "📅 本日の予定をお忘れなく！",
                            "image": "calendar.png"
                        },
                        {
                            "text": "⏰ リマインダー：重要なタスクをご確認ください。",
                            "image": null
                        }
                    ],
                    "custom": [
                        {
                            "text": "カスタムメッセージ1",
                            "image": "custom_image.jpg"
                        },
                        {
                            "text": "カスタムメッセージ2",
                            "image": null
                        }
                    ]
                },
                "recipients": [
                    {
                        "user_id": "USER_ID_1",
                        "username": "username1",
                        "message_category": "greeting",
                        "custom_messages": [],
                        "enabled": True
                    },
                    {
                        "user_id": "USER_ID_2",
                        "username": "username2",
                        "message_category": "reminder",
                        "custom_messages": [
                            {
                                "text": "このユーザー専用のメッセージ1",
                                "image": "special_image.png"
                            },
                            {
                                "text": "このユーザー専用のメッセージ2",
                                "image": null
                            }
                        ],
                        "enabled": True
                    }
                ]
            }
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(template, f, ensure_ascii=False, indent=2)
            raise FileNotFoundError(
                f"設定ファイル '{config_file}' を作成しました。"
                "APIキーと送信先情報を設定してください。"
            )

    def authenticate(self) -> tweepy.API:
        """
        Twitter API v1.1の認証

        Returns:
            認証済みのAPIオブジェクト
        """
        try:
            creds = self.config['api_credentials']
            auth = tweepy.OAuthHandler(
                creds['api_key'],
                creds['api_secret']
            )
            auth.set_access_token(
                creds['access_token'],
                creds['access_token_secret']
            )
            api = tweepy.API(auth, wait_on_rate_limit=True)

            # 認証確認
            api.verify_credentials()
            logging.info("Twitter API v1.1 認証成功")
            return api

        except Exception as e:
            logging.error(f"認証エラー: {e}")
            raise

    def authenticate_v2(self) -> tweepy.Client:
        """
        Twitter API v2の認証

        Returns:
            認証済みのClientオブジェクト
        """
        try:
            creds = self.config['api_credentials']
            client = tweepy.Client(
                bearer_token=creds.get('bearer_token'),
                consumer_key=creds['api_key'],
                consumer_secret=creds['api_secret'],
                access_token=creds['access_token'],
                access_token_secret=creds['access_token_secret'],
                wait_on_rate_limit=True
            )
            logging.info("Twitter API v2 認証成功")
            return client

        except Exception as e:
            logging.error(f"API v2 認証エラー: {e}")
            raise

    def upload_media(self, image_path: str) -> Optional[str]:
        """
        画像をアップロードしてメディアIDを取得

        Args:
            image_path: 画像ファイルのパス

        Returns:
            メディアID（失敗時はNone）
        """
        try:
            if not os.path.exists(image_path):
                logging.warning(f"画像ファイルが見つかりません: {image_path}")
                return None

            # ファイルサイズチェック
            max_size = self.config.get('media_settings', {}).get('max_image_size_mb', 5)
            file_size_mb = os.path.getsize(image_path) / (1024 * 1024)
            if file_size_mb > max_size:
                logging.warning(f"画像サイズが大きすぎます: {image_path} ({file_size_mb:.2f}MB)")
                return None

            # 画像アップロード（v1.1 API使用）
            media = self.api.media_upload(filename=image_path)
            logging.info(f"画像アップロード成功: {image_path} -> media_id: {media.media_id_string}")
            return media.media_id_string

        except Exception as e:
            logging.error(f"画像アップロードエラー: {e}")
            return None

    def send_dm(self, recipient_id: str, message: str, media_id: Optional[str] = None) -> bool:
        """
        DMを送信する（画像付き対応）

        Args:
            recipient_id: 受信者のユーザーID
            message: 送信するメッセージ
            media_id: メディアID（画像を添付する場合）

        Returns:
            送信成功の場合True
        """
        try:
            # DM送信パラメータ
            dm_params = {
                "dm_conversation_id": None,
                "participant_id": recipient_id,
                "text": message
            }

            # 画像がある場合はメディアIDを追加
            if media_id:
                dm_params["media_id"] = media_id

            # API v2を使用してDMを送信
            response = self.client.create_direct_message(**dm_params)

            if response.data:
                logging.info(
                    f"DM送信成功: {recipient_id}宛 - {message[:30]}... (画像: {'あり' if media_id else 'なし'})")
                return True
            else:
                logging.warning(f"DM送信失敗: {recipient_id}宛")
                return False

        except tweepy.errors.Forbidden as e:
            logging.error(f"権限エラー: {e}")
            logging.error("DMを送信する権限がないか、相手がDMを受け取れない設定です")
            return False
        except Exception as e:
            logging.error(f"DM送信エラー: {e}")
            return False

    def get_image_path(self, image_filename: Optional[str]) -> Optional[str]:
        """
        画像ファイルのフルパスを取得

        Args:
            image_filename: 画像ファイル名

        Returns:
            画像ファイルのフルパス（存在しない場合はNone）
        """
        if not image_filename:
            return None

        images_dir = self.config.get('media_settings', {}).get('images_directory', 'images')
        image_path = os.path.join(images_dir, image_filename)

        if os.path.exists(image_path):
            return image_path
        else:
            # 絶対パスとして試す
            if os.path.exists(image_filename):
                return image_filename

            logging.warning(f"画像ファイルが見つかりません: {image_filename}")
            return None

    def get_messages_for_recipient(self, recipient: Dict) -> List[Dict]:
        """
        受信者用のメッセージリストを取得

        Args:
            recipient: 受信者の設定

        Returns:
            メッセージのリスト（textとimageを含む辞書のリスト）
        """
        # カスタムメッセージが設定されている場合はそれを使用
        if recipient.get('custom_messages'):
            messages = recipient['custom_messages']
        else:
            # メッセージカテゴリーから取得
            category = recipient.get('message_category', 'custom')
            message_templates = self.config.get('message_templates', {})
            messages = message_templates.get(category, [{"text": "デフォルトメッセージ", "image": None}])

        # 古い形式（文字列のリスト）との互換性対応
        normalized_messages = []
        for msg in messages:
            if isinstance(msg, str):
                normalized_messages.append({"text": msg, "image": None})
            else:
                normalized_messages.append(msg)

        return normalized_messages

    def send_scheduled_messages(self):
        """スケジュールされたメッセージを送信"""
        logging.info("定期メッセージ送信開始")

        settings = self.config.get('schedule_settings', {})
        enable_timestamp = settings.get('enable_timestamp', True)
        randomize = settings.get('randomize_messages', False)

        for recipient in self.config.get('recipients', []):
            # 無効化されている受信者はスキップ
            if not recipient.get('enabled', True):
                logging.info(f"スキップ: {recipient.get('username')} - 無効化されています")
                continue

            user_id = recipient.get('user_id')
            username = recipient.get('username', 'Unknown')

            if not user_id:
                logging.warning(f"スキップ: {username} - ユーザーIDが設定されていません")
                continue

            # メッセージを取得
            messages = self.get_messages_for_recipient(recipient)

            if not messages:
                logging.warning(f"スキップ: {username} - メッセージが設定されていません")
                continue

            # メッセージを選択
            if randomize:
                message_data = random.choice(messages)
            else:
                # 順番に送信（ローテーション）
                message_index = self.get_message_index(user_id)
                message_data = messages[message_index % len(messages)]
                self.update_message_index(user_id, message_index + 1)

            # メッセージテキストを取得
            message_text = message_data.get('text', '') if isinstance(message_data, dict) else message_data

            # タイムスタンプを追加（オプション）
            if enable_timestamp:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                full_message = f"{message_text}\n\n送信時刻: {timestamp}"
            else:
                full_message = message_text

            # 画像の処理
            media_id = None
            if isinstance(message_data, dict) and message_data.get('image'):
                image_path = self.get_image_path(message_data['image'])
                if image_path:
                    media_id = self.upload_media(image_path)

            # DM送信
            success = self.send_dm(user_id, full_message, media_id)

            if success:
                logging.info(f"送信成功: {username} ({user_id})")
            else:
                logging.warning(f"送信失敗: {username} ({user_id})")

            # レート制限を避けるため少し待機
            time.sleep(2)

        logging.info("定期メッセージ送信完了")

    def get_message_index(self, user_id: str) -> int:
        """
        ユーザーごとのメッセージインデックスを取得

        Args:
            user_id: ユーザーID

        Returns:
            メッセージインデックス
        """
        index_file = 'message_index.json'
        if os.path.exists(index_file):
            with open(index_file, 'r') as f:
                indices = json.load(f)
                return indices.get(user_id, 0)
        return 0

    def update_message_index(self, user_id: str, index: int):
        """
        メッセージインデックスを更新

        Args:
            user_id: ユーザーID
            index: 新しいインデックス
        """
        index_file = 'message_index.json'
        indices = {}

        if os.path.exists(index_file):
            with open(index_file, 'r') as f:
                indices = json.load(f)

        indices[user_id] = index

        with open(index_file, 'w') as f:
            json.dump(indices, f)

    def start_scheduler(self):
        """スケジューラーを開始"""
        settings = self.config.get('schedule_settings', {})
        interval_hours = settings.get('interval_hours', 6)

        # 画像ディレクトリの作成
        images_dir = self.config.get('media_settings', {}).get('images_directory', 'images')
        if not os.path.exists(images_dir):
            os.makedirs(images_dir)
            logging.info(f"画像ディレクトリを作成しました: {images_dir}")

        # 初回実行
        self.send_scheduled_messages()

        # 定期実行の設定
        schedule.every(interval_hours).hours.do(self.send_scheduled_messages)

        logging.info(f"スケジューラー開始: {interval_hours}時間ごとに実行")
        logging.info("Ctrl+Cで停止できます")

        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # 1分ごとにチェック
        except KeyboardInterrupt:
            logging.info("スケジューラーを停止しました")
        except Exception as e:
            logging.error(f"予期しないエラー: {e}")
            raise


class ConfigManager:
    """設定ファイルを管理するクラス"""

    @staticmethod
    def validate_config(config: Dict) -> bool:
        """
        設定ファイルの検証

        Args:
            config: 設定辞書

        Returns:
            検証成功の場合True
        """
        required_fields = {
            'api_credentials': ['api_key', 'api_secret', 'access_token', 'access_token_secret'],
            'schedule_settings': ['interval_hours'],
            'recipients': []
        }

        # 必須フィールドの確認
        for field, subfields in required_fields.items():
            if field not in config:
                logging.error(f"必須フィールド '{field}' が見つかりません")
                return False

            for subfield in subfields:
                if subfield not in config[field]:
                    logging.error(f"必須フィールド '{field}.{subfield}' が見つかりません")
                    return False

        # APIキーが設定されているか確認
        creds = config['api_credentials']
        if creds['api_key'] == 'YOUR_API_KEY':
            logging.error("APIキーが設定されていません")
            return False

        # 受信者が設定されているか確認
        if not config.get('recipients'):
            logging.warning("受信者が設定されていません")

        return True

    @staticmethod
    def add_message_template(config_file: str, category: str, messages: List[Dict]):
        """
        メッセージテンプレートを追加

        Args:
            config_file: 設定ファイルのパス
            category: カテゴリー名
            messages: メッセージリスト（textとimageを含む辞書のリスト）
        """
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        if 'message_templates' not in config:
            config['message_templates'] = {}

        config['message_templates'][category] = messages

        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        logging.info(f"メッセージテンプレート '{category}' を追加しました")

    @staticmethod
    def add_recipient(config_file: str, user_id: str, username: str,
                      message_category: str = 'custom', custom_messages: List[Dict] = None):
        """
        受信者を追加

        Args:
            config_file: 設定ファイルのパス
            user_id: ユーザーID
            username: ユーザー名
            message_category: メッセージカテゴリー
            custom_messages: カスタムメッセージ
        """
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        new_recipient = {
            "user_id": user_id,
            "username": username,
            "message_category": message_category,
            "custom_messages": custom_messages or [],
            "enabled": True
        }

        config['recipients'].append(new_recipient)

        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        logging.info(f"受信者 '{username}' を追加しました")


class MediaManager:
    """画像などのメディアファイルを管理するクラス"""

    @staticmethod
    def validate_image(image_path: str, max_size_mb: float = 5.0) -> bool:
        """
        画像ファイルの検証

        Args:
            image_path: 画像ファイルのパス
            max_size_mb: 最大ファイルサイズ（MB）

        Returns:
            検証成功の場合True
        """
        if not os.path.exists(image_path):
            return False

        # ファイルサイズチェック
        file_size_mb = os.path.getsize(image_path) / (1024 * 1024)
        if file_size_mb > max_size_mb:
            logging.warning(f"画像サイズが大きすぎます: {image_path} ({file_size_mb:.2f}MB)")
            return False

        # 拡張子チェック
        supported_formats = ['jpg', 'jpeg', 'png', 'gif', 'webp']
        extension = Path(image_path).suffix[1:].lower()
        if extension not in supported_formats:
            logging.warning(f"サポートされていない画像形式: {extension}")
            return False

        return True

    @staticmethod
    def organize_images(images_dir: str):
        """
        画像ファイルを整理

        Args:
            images_dir: 画像ディレクトリのパス
        """
        if not os.path.exists(images_dir):
            os.makedirs(images_dir)
            logging.info(f"画像ディレクトリを作成: {images_dir}")

        # サンプル画像の説明ファイルを作成
        readme_path = os.path.join(images_dir, 'README.txt')
        if not os.path.exists(readme_path):
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write("画像ファイルの配置方法\n")
                f.write("=" * 40 + "\n\n")
                f.write("1. このディレクトリに送信したい画像を配置してください\n")
                f.write("2. サポートされる形式: JPG, PNG, GIF, WebP\n")
                f.write("3. 最大ファイルサイズ: 5MB\n")
                f.write("4. config.jsonのメッセージ設定で画像ファイル名を指定\n\n")
                f.write("例:\n")
                f.write('  "image": "morning.jpg"\n')
                f.write('  "image": "calendar.png"\n')


def main():
    """メイン関数"""
    print("=" * 50)
    print("Twitter DM 定期送信プログラム（画像対応版）")
    print("=" * 50)
    print("\n重要な注意事項:")
    print("- Twitter/Xの利用規約を必ず遵守してください")
    print("- 受信者の同意を得てから使用してください")
    print("- スパムや迷惑行為は禁止されています")
    print("- APIレート制限に注意してください")
    print("=" * 50)

    try:
        # スケジューラーの初期化
        scheduler = TwitterDMScheduler('config.json')

        # 設定の検証
        if not ConfigManager.validate_config(scheduler.config):
            print("\n設定ファイルにエラーがあります。")
            print("config.jsonを確認してください。")
            return

        # 画像ディレクトリの準備
        images_dir = scheduler.config.get('media_settings', {}).get('images_directory', 'images')
        MediaManager.organize_images(images_dir)

        # 設定内容の表示
        settings = scheduler.config.get('schedule_settings', {})
        recipients = scheduler.config.get('recipients', [])
        enabled_recipients = [r for r in recipients if r.get('enabled', True)]

        print(f"\n設定内容:")
        print(f"- 送信間隔: {settings.get('interval_hours', 6)}時間")
        print(f"- タイムスタンプ: {'有効' if settings.get('enable_timestamp', True) else '無効'}")
        print(f"- ランダム送信: {'有効' if settings.get('randomize_messages', False) else '無効'}")
        print(f"- 有効な受信者数: {len(enabled_recipients)}人")
        print(f"- 画像ディレクトリ: {images_dir}")
        print("")

        # スケジューラーの開始
        scheduler.start_scheduler()

    except FileNotFoundError as e:
        print(f"\n{e}")
        print("\n設定手順:")
        print("1. config.jsonファイルを開く")
        print("2. Twitter Developer PortalでAPIキーを取得")
        print("3. config.jsonにAPIキーを設定")
        print("4. メッセージテンプレートを設定")
        print("5. 画像ファイルをimagesディレクトリに配置")
        print("6. 受信者情報を設定")
        print("7. プログラムを再実行")

    except Exception as e:
        logging.error(f"エラーが発生しました: {e}")
        print(f"\nエラー: {e}")
        print("ログファイル 'twitter_dm_log.txt' を確認してください")


if __name__ == "__main__":
    main()