from brownie import chain
from yearn.networks import Network

tokens_by_network = {
    Network.Mainnet: {
        'weth': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
        'usdc': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
        'dai': '0x6B175474E89094C44Da98b954EedeAC495271d0F',
    },
    Network.Fantom: {
        'weth': '0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83',
        'usdc': '0x04068DA6C83AFCFA0e13ba15A6696662335D5B75',
        'dai': '0x8D11eC38a3EB5E956B052f67Da8Bdc9bef8Abf3E',
    },
    Network.Arbitrum: {
        'weth': '0x82aF49447D8a07e3bd95BD0d56f35241523fBab1',
        'usdc': '0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8',
        'dai': '0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1',
    },
}

stablecoins_by_network = {
    Network.Mainnet: {
        "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48": "usdc",
        "0x0000000000085d4780B73119b644AE5ecd22b376": "tusd",
        "0x6B175474E89094C44Da98b954EedeAC495271d0F": "dai",
        "0xdAC17F958D2ee523a2206206994597C13D831ec7": "usdt",
        "0x4Fabb145d64652a948d72533023f6E7A623C7C53": "busd",
        "0x57Ab1ec28D129707052df4dF418D58a2D46d5f51": "susd",
        "0x1456688345527bE1f37E9e627DA0837D6f08C925": "usdp",
        "0x674C6Ad92Fd080e4004b2312b45f796a192D27a0": "usdn",
        "0x853d955aCEf822Db058eb8505911ED77F175b99e": "frax",
        "0x5f98805A4E8be255a32880FDeC7F6728C6568bA0": "lusd",
        "0xBC6DA0FE9aD5f3b0d58160288917AA56653660E9": "alusd",
        "0x0000000000085d4780B73119b644AE5ecd22b376": "tusd",
        "0x1c48f86ae57291F7686349F12601910BD8D470bb": "usdk",
        "0x056Fd409E1d7A124BD7017459dFEa2F387b6d5Cd": "gusd",
        "0x0E2EC54fC0B509F445631Bf4b91AB8168230C752": "linkusd",
    },
    Network.Fantom: {
        "0x04068DA6C83AFCFA0e13ba15A6696662335D5B75": "usdc",
        "0x8D11eC38a3EB5E956B052f67Da8Bdc9bef8Abf3E": "dai",
    },
    Network.Arbitrum: {
        '0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8': 'usdc',
        '0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1': 'dai',
    },
}

weth = tokens_by_network[chain.id]['weth']
usdc = tokens_by_network[chain.id]['usdc']
dai = tokens_by_network[chain.id]['dai']
stablecoins = stablecoins_by_network[chain.id]
