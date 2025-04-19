# -*- coding: utf-8 -*-

# -[ Imports ]-

import requests
from bs4 import BeautifulSoup

# -[ Constants ]-
# -[ Private ]-
# -[ Public ]-

def get_rom_list(url: str, platform: str, ext: str) -> list:
    """
    Get the list of roms from a given url
    :param url: The url to scrape
    :param ext: The extension of the roms
    :return: A list of roms
    """
    try:
        response = requests.get(url)
        response.raise_for_status()
        html_content = response.text

        soup = BeautifulSoup(html_content, 'html.parser')

        rows = soup.find_all('tr')

        result = []
        for row in rows:
            if row is not None:
                td_link = row.find('td', class_='link')
                td_size = row.find('td', class_='size')
                if td_link is not None:
                    link_tag = td_link.find('a')
                    if link_tag.get_text(strip=True).endswith(f'.{ext}'):
                        result.append({
                            'name': link_tag.get_text(strip=True).replace(f'.{ext}', ''),
                            'url': f"{url}{link_tag['href']}",
                            'size': td_size.get_text(strip=True),
                            'platform': platform
                        })

        return result

    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la récupération de la page : {e}")
        return []
    except Exception as e:
        print(f"Erreur générale : {e}")
        return []
