import os
import json
import requests
import argparse
from time import sleep
from itertools import count
from bs4 import BeautifulSoup
from pathvalidate import sanitize_filename
from urllib.parse import urljoin, urlparse, unquote


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

    title_tag = soup.select_one('h1')
    title, author = title_tag.text.split('::')

    txt_tag = soup.select_one('[href^="/txt."]')
    book_path = txt_tag['href'] if txt_tag else '/txt.php'

    image_src = soup.select_one('div.bookimage img')['src']

    comments = [tag.text for tag in soup.select('div.texts span.black')]

    genres = [tag.text for tag in soup.select('span.d_book a')]

    return {
        'title': title.strip(),
        'author': author.strip(),
        'book_path': book_path,
        'image_src': image_src,
        'comments': comments,
        'genres': genres,
    }


def parse_category_page(category_page, start_page=1, end_page=0):

    downloaded_books = []
    connect_wait = 10

    if end_page:
        pagination_range = range(start_page, end_page + 1)
    else:
        pagination_range = count(start_page)

    for pagination in pagination_range:

        url = urljoin(category_page, str(pagination))
        category_response = requests.get(url)
        category_response.raise_for_status()
        if category_response.history:
            print(f'Все страницы загружены! Последняя: {pagination - 1}')
            break

        soup = BeautifulSoup(category_response.text, 'lxml')

        links_selector = 'div.bookimage a'
        links = soup.select(links_selector)

        for link in links:
            connection = True

            while True:
                try:
                    response = fetch_book_page(
                        urljoin(category_response.url, link['href'])
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
                        f'Книга по адресу: {link["href"]} ',
                        f'не доступна для скачивания.\n'
                    )
                    break
                except Exception as error:
                    print(f'\nНепредвиденная ошибка: {error}')
                    print(
                        f'\nКнига по адресу: {link["href"]} ',
                        f'Проверьте! Возможна ошибка при загрузке.\n'
                    )

    with open('books.json', 'w', encoding='utf-8') as file:
        file.write(
            json.dumps(
                downloaded_books,
                indent=True,
                ensure_ascii=False
            )
        )


def create_parser():
    parser = argparse.ArgumentParser(
        description='Парсинг книг по категириям с сайта tululu.org '
    )

    parser.add_argument(
        '--category_page',
        help='Ссылка на категорию книг. По умолчанию: \
            https://tululu.org/l55/ - фантастика',
        default='https://tululu.org/l55/'
    )
    parser.add_argument(
        '--start_page',
        help='Начальная страница (int) для парсинга',
        type=int,
        default=1
    )
    parser.add_argument(
        '--end_page',
        help='Конечная страница (int) для парсинга',
        type=int,
        default=0
    )

    return parser


if __name__ == '__main__':

    parser = create_parser()
    args = parser.parse_args()

    parse_category_page(
        category_page=args.category_page,
        start_page=args.start_page,
        end_page=args.end_page
    )
