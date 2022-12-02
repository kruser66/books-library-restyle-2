import os
import re
import sys
import requests
import argparse
from time import sleep
from bs4 import BeautifulSoup
from pathvalidate import sanitize_filename
from urllib.parse import urljoin, urlparse, unquote
import json
from pprint import pprint


def check_for_redirect(response):

    if response.history:
        raise requests.HTTPError


def fetch_book_page(book_url):

    response = requests.get(book_url)
    response.raise_for_status()
    check_for_redirect(response)

    return response


def download_txt(url, filename, folder='books/'):
    """Функция для скачивания текстовых файлов.
    Args:
        url (str): Cсылка на текст, который хочется скачать.
        filename (str): Имя файла, с которым сохранять.
        folder (str): Папка, куда сохранять.
    Returns:
        str: Путь до файла, куда сохранён текст.
    """
    os.makedirs(folder, exist_ok=True)

    response = requests.get(url)
    response.raise_for_status()
    check_for_redirect(response)

    path_to_save = os.path.join(folder, sanitize_filename(filename) + '.txt')

    with open(path_to_save, 'wb') as file:
        file.write(response.content)

    print(path_to_save)

    return path_to_save


def download_cover(url, filename, folder='images/'):
    """Функция для скачивания изображений книг.
    Args:
        url (str): Cсылка на картинку, которую хочется скачать.
        filename (str): Имя файла, с которым сохранять.
        folder (str): Папка, куда сохранять.
    Returns:
        str: Путь до файла, куда сохранёна картинка.
    """
    os.makedirs(folder, exist_ok=True)

    response = requests.get(url)
    response.raise_for_status()
    check_for_redirect(response)

    path_to_save = os.path.join(folder, sanitize_filename(filename))

    with open(path_to_save, 'wb') as file:
        file.write(response.content)

    print(path_to_save)

    return path_to_save


def parse_book_page(response):

    soup = BeautifulSoup(response.text, 'lxml')

    title_tag = soup.find('h1')
    title, author = title_tag.text.split('::')

    txt_tag = soup.find(href=re.compile("/txt."))
    book_path = txt_tag['href'] if txt_tag else '/txt.php'

    image_tag = soup.find('div', class_='bookimage').find('img')
    image_src = image_tag['src']

    tag_comments = soup.find_all('div', class_='texts')
    comments = [tag.find('span').text for tag in tag_comments]

    tag_genre = soup.find('span', class_='d_book').find_all('a')
    genres = [tag.text for tag in tag_genre]

    return {
        'title': title.strip(),
        'author': author.strip(),
        'image_src': image_src,
        'book_path': book_path,
        'comments': comments,
        'genres': genres,
    }


def create_parser():
    parser = argparse.ArgumentParser(
        description='Парсинг книг с сайта tululu.org '
    )

    parser.add_argument(
        'start_id',
        help='Начальный индекс (int) для парсинга',
        type=int
    )
    parser.add_argument(
        'end_id',
        help='Конечный индекс (int) конечный индекс',
        type=int
    )

    return parser


def parse_category_page(category_page, pages):

    downloaded_books = []
    connect_wait = 10

    for pagination in range(1, pages + 1):

        url = urljoin(category_page, str(pagination))
        response = requests.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'lxml')

        links = soup.find_all('div', class_='bookimage')

        for link in links:
            connection = True
            while True:
                try:
                    response = fetch_book_page(
                        urljoin(response.url, link.a['href'])
                    )
                    book = parse_book_page(response)

                    cover_name = unquote(
                        urlparse(book['image_src']).path.split('/')[-1]
                    )

                    book['book_path'] = download_txt(
                        urljoin(response.url, book['book_path']),
                        book['title'])
                    book['image_src'] = download_cover(
                        urljoin(response.url, book['image_src']),
                        cover_name)
                    print()

                    downloaded_books.append(book)
                    break
                except requests.ConnectionError:
                    if connection:
                        connection = False
                        print(
                            f'\nОтсутствует соединение с Интернет!'
                            f'Повторная попытка соединения...'
                        )
                    else:
                        print('\nОтсутствует соединение с Интернет!')
                        print(
                            f'Повторная попытка соединения через'
                            f' {connect_wait} секунд.'
                        )
                        sleep(connect_wait)
                except requests.HTTPError:
                    print(
                        f'Книга по адресу: {link.a["href"]} ',
                        f'не доступна для скачивания.\n'
                    )
                    break
                except Exception as error:
                    print(f'\nНепредвиденная ошибка: {error}')
                    print(
                        f'\nКнига по адресу: {link.a["href"]} ',
                        f'Проверьте! Возможна ошибка при загрузке.\n'
                    )

        pprint(downloaded_books)

        with open('books.json', 'w', encoding='utf-8') as file:
            file.write(
                json.dumps(
                    downloaded_books,
                    indent=True,
                    ensure_ascii=False
                )
            )


if __name__ == '__main__':

    category_page = 'https://tululu.org/l55/'
    parse_category_page(category_page, 1)
