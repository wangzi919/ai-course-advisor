from abc import ABC, abstractmethod
import requests
import logging
import shutil
from pathlib import Path
from datetime import datetime
import json
from typing import List, Dict, Any, Optional

# 使用標準 logging,讓 run_*.py 的設定統一管理
logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """爬蟲基礎類別，所有爬蟲都應該繼承此類別"""

    def __init__(
        self,
        source_url: str,
        output_filename: str,
        data_dir: str = "activities",
        enable_hot_reload: bool = True,
        pm2_services: Optional[List[str]] = None
    ):
        """
        初始化爬蟲

        Args:
            source_url: 要爬取的網站來源
            output_filename: 輸出檔案名稱 (不含路徑)
            data_dir: 資料子目錄名稱，會建立在 project_root/data/{data_dir}，預設為 "activities"
            enable_hot_reload: 是否啟用熱重載（預設 True）
            pm2_services: PM2 服務名稱列表（預設 ['claude-mcp-server']）
        """
        self.source_url = source_url
        self.output_filename = output_filename
        self.enable_hot_reload = enable_hot_reload
        self.pm2_services = pm2_services or ['claude-mcp-server']

        # 設定專案路徑
        project_root = Path(__file__).parent.parent
        self.data_dir = project_root / "data" / data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.output_path = self.data_dir / output_filename

        # 設定 requests session
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
        }

    def check_and_scrape(self):
        """檢查本地是否有檔案，沒有的話執行爬蟲"""
        if self.output_path.exists():
            logger.info(f"檔案已存在: {self.output_path}")
            return self.load_data()
        else:
            logger.info(f"檔案不存在，開始爬取: {self.source_url}")
            return self.run()

    def run(self):
        """執行完整爬蟲流程"""
        logger.info("=" * 50)
        logger.info(f"開始爬取: {self.source_url}")
        logger.info("=" * 50)

        # 抓取資料
        raw_data = self.scrape()

        if not raw_data:
            logger.warning("未抓取到任何資料")
            return []

        # 解析資料
        parsed_data = self.parse(raw_data)

        # 儲存資料
        self.save_data(parsed_data)

        logger.info("=" * 50)
        logger.info(f"爬蟲完成! 共抓取 {len(parsed_data)} 筆資料")
        logger.info("=" * 50)

        return parsed_data

    @abstractmethod
    def scrape(self) -> Any:
        """
        爬取資料的方法 (必須實作)

        Returns:
            原始資料，格式依各爬蟲而定
        """
        pass

    @abstractmethod
    def parse(self, raw_data: Any) -> List[Dict]:
        """
        解析資料的方法 (必須實作)

        Args:
            raw_data: scrape() 方法回傳的原始資料

        Returns:
            解析後的資料列表
        """
        pass

    def fetch_page(self, url: str, timeout: int = 10) -> str:
        """
        通用的網頁抓取方法

        Args:
            url: 要抓取的 URL
            timeout: 逾時時間

        Returns:
            網頁 HTML 內容
        """
        try:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            logger.info(f"正在抓取: {url}")
            response = self.session.get(
                url, headers=self.headers, timeout=timeout, verify=False)
            response.raise_for_status()
            response.encoding = 'utf-8'
            return response.text
        except requests.RequestException as e:
            logger.error(f"抓取失敗 {url}: {str(e)}")
            return None

    def save_data(self, data: List[Dict]):
        """
        儲存資料為 JSON 檔案，自動加上 metadata

        Args:
            data: 要儲存的資料列表
        """
        try:
            result = {
                "metadata": {
                    "last_updated": datetime.now().isoformat(),
                    "total_count": len(data),
                    "data_source": self.source_url
                },
                "data": data
            }

            with open(self.output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            logger.info(f"資料已儲存至: {self.output_path}")
            logger.info(f"Metadata - 最後更新: {result['metadata']['last_updated']}, "
                        f"總數: {result['metadata']['total_count']}")

            # 觸發熱重載
            if self.enable_hot_reload:
                self._trigger_hot_reload()
        except Exception as e:
            logger.error(f"儲存資料時發生錯誤: {str(e)}")

    def load_data(self) -> List[Dict]:
        """
        載入本地 JSON 檔案

        Returns:
            資料列表
        """
        try:
            with open(self.output_path, 'r', encoding='utf-8') as f:
                result = json.load(f)

            logger.info(f"已載入資料: {self.output_path}")
            logger.info(f"Metadata - 最後更新: {result['metadata']['last_updated']}, "
                        f"總數: {result['metadata']['total_count']}")

            return result.get('data', [])
        except Exception as e:
            logger.error(f"載入資料時發生錯誤: {str(e)}")
            return []

    def _trigger_hot_reload(self):
        """
        觸發熱重載機制

        使用 utils/hot_reload.py 的功能來更新檔案時間戳並重啟 PM2 服務
        """
        try:
            from utils.hot_reload import hot_reload_after_scraping

            logger.info("🔥 觸發熱重載機制...")
            hot_reload_after_scraping(
                data_file_path=str(self.output_path),
                pm2_services=self.pm2_services,
                use_pm2_reload=True
            )
            logger.info("✅ 熱重載完成")
        except ImportError:
            logger.warning("⚠ 無法載入 hot_reload 模組，跳過熱重載")
        except Exception as e:
            logger.warning(f"⚠ 熱重載失敗: {e}")

    def clear_html_cache(self):
        """清除 HTML 快取資料夾"""
        # 檢查子類別是否有定義 html_cache_dir 屬性
        if hasattr(self, 'html_cache_dir'):
            cache_dir = self.html_cache_dir
            if isinstance(cache_dir, Path) and cache_dir.exists():
                try:
                    shutil.rmtree(cache_dir)
                    logger.info(f"✓ 已清除 HTML 快取: {cache_dir}")
                    # 重新建立空資料夾
                    cache_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    logger.warning(f"清除 HTML 快取失敗: {e}")

    def force_update(self):
        """強制更新資料（不管本地是否有檔案，並清除 HTML 快取）"""
        logger.info("強制更新模式")
        # 清除 HTML 快取（如果有的話）
        self.clear_html_cache()
        return self.run()
