# from better_proxy import Proxy
from fake_useragent import UserAgent
import aiohttp
from tenacity import retry, stop_after_attempt, wait_random

from utils import logger


class BaseClient:
    def __init__(self, proxy: str = None):
        self.session = None
        self.ip = None
        self.username = None

        self.user_agent = UserAgent().random
        self.proxy = ""  # proxy and Proxy.from_str(proxy).as_url

        self.website_headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'en-US,en;q=0.9',
            'origin': 'https://www.grassfoundation.io',
            'priority': 'u=1, i',
            'referer': 'https://www.grassfoundation.io/',
            'sec-ch-ua': '"Not)A;Brand";v="99", "Google Chrome";v="127", "Chromium";v="127"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'cross-site',
            'user-agent': self.user_agent,
        }

        self.session = aiohttp.ClientSession(headers=self.website_headers)

    @retry(stop=stop_after_attempt(5), wait=wait_random(min=1, max=3), reraise=True,
           before_sleep=lambda retry_state, **kwargs: logger.warning(f"Send request error | "
                                                                  f"{retry_state.outcome.exception()} "), )
    async def make_request(self, method: str, url: str, **kwargs):
        if self.proxy:
            kwargs['proxy'] = self.proxy

        return await self.session.request(method, url, **kwargs)

    async def close(self):
        if self.session:
            await self.session.close()
