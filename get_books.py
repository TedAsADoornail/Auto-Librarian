import subprocess
from datetime import datetime

import feedparser
import re
import time
import send_to_kindle
import libgenapi
import requests
from urllib.request import urlopen
import bs4
import csv
import traceback
from pathlib import Path
import unicodedata

from libgen_api.libgen_search import search_title, filter_results

MIRROR_SOURCES = ["GET", "Cloudflare", "IPFS.io", "Infura"]

sent_books_csv = 'sent_books/sent_books.csv'


def get_books_from_shelf(userid, shelf_name):
    rss_url = "https://www.goodreads.com/review/list_rss/" + userid + "?shelf=" + shelf_name
    parsed_rss = feedparser.parse(rss_url)
    book_ids = []
    for entry in parsed_rss["entries"]:
        book_ids.append(entry["book_id"])
    return book_ids


def get_all_lists(soup):
    lists = []
    list_count_dict = {}

    if soup.find('a', text='More lists with this book...'):

        lists_url = soup.find('a', text='More lists with this book...')['href']

        source = urlopen('https://www.goodreads.com' + lists_url)
        soup = bs4.BeautifulSoup(source, 'lxml')
        lists += [' '.join(node.text.strip().split()) for node in soup.find_all('div', {'class': 'cell'})]

        i = 0
        while soup.find('a', {'class': 'next_page'}) and i <= 10:
            time.sleep(2)
            next_url = 'https://www.goodreads.com' + soup.find('a', {'class': 'next_page'})['href']
            source = urlopen(next_url)
            soup = bs4.BeautifulSoup(source, 'lxml')

            lists += [node.text for node in soup.find_all('div', {'class': 'cell'})]
            i += 1

        # Format lists text.
        for _list in lists:
            # _list_name = ' '.join(_list.split()[:-8])
            # _list_rank = int(_list.split()[-8][:-2]) 
            # _num_books_on_list = int(_list.split()[-5].replace(',', ''))
            # list_count_dict[_list_name] = _list_rank / float(_num_books_on_list)     # TODO: switch this back to raw counts
            _list_name = _list.split()[:-2][0]
            _list_count = int(_list.split()[-2].replace(',', ''))
            list_count_dict[_list_name] = _list_count

    return list_count_dict


def get_shelves(soup):
    shelf_count_dict = {}

    if soup.find('a', text='See top shelves…'):

        # Find shelves text.
        shelves_url = soup.find('a', text='See top shelves…')['href']
        source = urlopen('https://www.goodreads.com' + shelves_url)
        soup = bs4.BeautifulSoup(source, 'lxml')
        shelves = [' '.join(node.text.strip().split()) for node in soup.find_all('div', {'class': 'shelfStat'})]

        # Format shelves text.
        shelf_count_dict = {}
        for _shelf in shelves:
            _shelf_name = _shelf.split()[:-2][0]
            _shelf_count = int(_shelf.split()[-2].replace(',', ''))
            shelf_count_dict[_shelf_name] = _shelf_count

    return shelf_count_dict


def get_genres(soup):
    genres = []
    for node in soup.find_all('div', {'class': 'left'}):
        current_genres = node.find_all('a', {'class': 'actionLinkLite bookPageGenreLink'})
        current_genre = ' > '.join([g.text for g in current_genres])
        if current_genre.strip():
            genres.append(current_genre)
    return genres


def get_series_name(soup):
    series = soup.find(id="bookSeries").find("a")
    if series:
        series_name = re.search(r'\((.*?)\)', series.text).group(1)
        return series_name
    else:
        return ""


def get_series_uri(soup):
    series = soup.find(id="bookSeries").find("a")
    if series:
        series_uri = series.get("href")
        return series_uri
    else:
        return ""


def get_isbn(soup):
    try:
        isbn = re.findall(r'nisbn: [0-9]{10}', str(soup))[0].split()[1]
        return isbn
    except:
        return "isbn not found"


def get_isbn13(soup):
    try:
        isbn13 = re.findall(r'nisbn13: [0-9]{13}', str(soup))[0].split()[1]
        return isbn13
    except:
        return "isbn13 not found"


def get_rating_distribution(soup):
    distribution = re.findall(r'renderRatingGraph\([\s]*\[[0-9,\s]+', str(soup))[0]
    distribution = ' '.join(distribution.split())
    distribution = [int(c.strip()) for c in distribution.split('[')[1].split(',')]
    distribution_dict = {'5 Stars': distribution[0],
                         '4 Stars': distribution[1],
                         '3 Stars': distribution[2],
                         '2 Stars': distribution[3],
                         '1 Star': distribution[4]}
    return distribution_dict


def get_num_pages(soup):
    if soup.find('span', {'itemprop': 'numberOfPages'}):
        num_pages = soup.find('span', {'itemprop': 'numberOfPages'}).text.strip()
        return int(num_pages.split()[0])
    return ''


def get_year_first_published(soup):
    year_first_published = soup.find('nobr', attrs={'class': 'greyText'})
    if year_first_published:
        year_first_published = year_first_published.string
        return re.search('([0-9]{3,4})', year_first_published).group(1)
    else:
        return ''


def get_id(book_id):
    pattern = re.compile("([^.-]+)")
    return pattern.search(book_id).group()


def scrape_book(book_id):
    url = 'https://www.goodreads.com/book/show/' + book_id
    source = urlopen(url)
    soup = bs4.BeautifulSoup(source, 'html.parser')
    soup.prettify(formatter='html')

    time.sleep(2)

    return {'book_id_title': book_id,
            'book_id': get_id(book_id),
            'book_title': soup.find('h1', {'id': 'bookTitle'}).getText().strip().replace('\\', ''),
            "book_series": get_series_name(soup),
            "book_series_uri": get_series_uri(soup),
            'isbn': get_isbn(soup),
            'isbn13': get_isbn13(soup),
            # 'year_first_published': get_year_first_published(soup),
            'author': ' '.join(soup.find('span', {'itemprop': 'name'}).text.split()),
            'num_pages': get_num_pages(soup),
            'genres': get_genres(soup),
            # 'shelves': get_shelves(soup),
            # 'lists': get_all_lists(soup),
            # 'num_ratings': soup.find('meta', {'itemprop': 'ratingCount'})['content'].strip(),
            # 'num_reviews': soup.find('meta', {'itemprop': 'reviewCount'})['content'].strip(),
            # 'average_rating': soup.find('span', {'itemprop': 'ratingValue'}).text.strip(),
            # 'rating_distribution': get_rating_distribution(soup)
            }


def scrape_title(book_id):
    url = 'https://www.goodreads.com/book/show/' + book_id
    source = urlopen(url)
    soup = bs4.BeautifulSoup(source, 'html.parser')
    return ' '.join(soup.find('h1', {'id': 'bookTitle'}).text.split()).replace("\\", "")


def scrape_isbn(book_id):
    url = 'https://www.goodreads.com/book/show/' + book_id
    source = urlopen(url)
    soup = bs4.BeautifulSoup(source, 'html.parser')
    return get_isbn(soup)


def download_books(download_links):
    if download_links != 0:
        print('We have {0} many links'.format(len(download_links)))
        for key, value in download_links.items():
            try:
                response = urlopen(value)
            except Exception as exception:
                print('Cannot download book because {0}'.format(exception))
            else:
                return response.read()
        print('=============================')
    else:
        print('No MOBIs of this book found :(')


def search_for_a_book_by_isbn(isbn):
    try:
        libgen_search = libgenapi.Libgenapi(["http://libgen.rs", "http://libgen.is/"])
        return list(libgen_search.search(isbn, "identifier"))[0]
    except Exception as exception:
        return 0


def get_file_name(book):
    return slugify(book.get('Title')) + '.' + book.get('Extension')


def slugify(value, allow_unicode=False):
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize('NFKC', value)
    else:
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value.lower())
    return re.sub(r'[-\s]+', '-', value).strip('-_')


def resolve_fiction_download_links(mirrors):
    mirror_1 = mirrors[0]
    page = requests.get(mirror_1)
    soup = bs4.BeautifulSoup(page.text, "html.parser")
    links = soup.find_all("a", string=MIRROR_SOURCES)
    download_links = {link.string: link["href"] for link in links}
    return download_links


def resolve_nonfiction_download_links(book):
    mirror_1 = book["Mirror_1"]
    page = requests.get(mirror_1)
    soup = bs4.BeautifulSoup(page.text, "html.parser")
    links = soup.find_all("a", string=MIRROR_SOURCES)
    download_links = {link.string: link["href"] for link in links}
    return download_links


def write_book_to_file(file_name, file):
    with open('books/' + file_name, "wb") as binary_file:
        binary_file.write(file)
        return 0


def convert_epub_to_mobi(file_name):
    subprocess.call(["ebook-convert", 'books/' + file_name, 'books/' + file_name.replace("epub", "mobi")])
    return file_name.replace(file_name.split('.')[1], 'mobi')


def search_for_a_fiction_book_by_title(title):
    try:
        results = search_title('fiction', title)
        filtered_results = filter_results(results, {'Title': title, 'Extension': 'mobi'}, True)
        if title == results[0].get('Title'):
            print('These are actually the same...')
        if filtered_results:
            return filtered_results
        else:
            filtered_results = filter_results(results, {'Title': title, 'Extension': 'epub'}, True)
            return filtered_results
    except:
        return 0


def search_for_a_nonfiction_book_by_title(title):
    try:
        results = search_title('nonfiction', title)
        filtered_results = filter_results(results, {'Title': title, 'Extension': 'mobi'}, True)
        if filtered_results:
            return filtered_results
        else:
            return filter_results(results, {'Title': title, 'Extension': 'epub'}, True)
    except Exception as exception:
        return exception


def write_sent_book_id(book_id):
    with open(sent_books_csv, 'a', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow([book_id])


def main():
    user_id = '50601648-ted'
    shelf = 'to-read'
    book_file = Path(sent_books_csv)
    book_file.touch(exist_ok=True)
    with open(sent_books_csv) as csv_file_name:
        reader = csv.reader(csv_file_name)
        books_already_scraped = [row[0] for row in reader]
    books_from_shelf = get_books_from_shelf(user_id, shelf)
    books_to_scrape = [book_id for book_id in books_from_shelf if book_id not in books_already_scraped]
    print('We\'re going to try to download {0} books now!'.format(len(books_to_scrape)))
    for book_id in books_to_scrape:
        scraped_book = scrape_book(book_id)
        book_title = scraped_book.get('book_title')
        print('I am going to try to find {0} now!'.format(book_title))
        try:
            book = search_for_a_fiction_book_by_title(book_title)
            if not book:
                book = search_for_a_nonfiction_book_by_title(book_title)[0]
                download_links = resolve_nonfiction_download_links(book)
            else:
                book = book[0]
                download_links = resolve_fiction_download_links(book.get('Mirrors'))
            print('Downloading ' + book_title)

            downloaded_file = download_books(download_links)
            file_name = get_file_name(book)
            if downloaded_file is not None:
                write_book_to_file(file_name, downloaded_file)
                if 'epub' in file_name:
                    file_name = convert_epub_to_mobi(file_name)
                result = send_to_kindle.send_book_to_kindle_email(file_name)
                if result == 1:
                    write_sent_book_id(book_id)

        except Exception as exception:
            traceback.print_exc()
            print(exception)


if __name__ == '__main__':
    main()
