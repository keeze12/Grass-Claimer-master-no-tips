from tenacity import stop_after_attempt, wait_random, retry

from utils.session import BaseClient

import base58
from solders.keypair import Keypair


class GrassFoundation(BaseClient):
    def __init__(self, private_key: str, proxy: str = None):
        super().__init__(proxy)
        self.private_key = private_key
        self.keypair = Keypair.from_bytes(base58.b58decode(private_key))
        self.address = str(self.keypair.pubkey())

        self.headers = {
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
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
        }

    @retry(stop=stop_after_attempt(50), wait=wait_random(min=1, max=3), reraise=True)
    async def get_sign_msg(self):
        url = f'https://api.getgrass.io/airdropClaimReceipt?input=%7B%22walletAddress%22:%22{self.address}%22,%22cluster%22:%22mainnet%22%7D'

        response = await self.session.get(url, headers=self.headers)

        resp_json = await response.json()

        return resp_json['result']['data']
