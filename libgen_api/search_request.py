import urllib

import requests
from bs4 import BeautifulSoup

genre_table_ints = {'fiction': 0, 'nonfiction': 2}


def strip_i_tag_from_soup(soup):
    subheadings = soup.find_all("i")
    for subheading in subheadings:
        subheading.decompose()


def get_information_table(soup, genre):
    return soup.find_all("table")[genre_table_ints.get(genre)]


def get_all_fiction_mirrors(td):
    output = []
    for link in td.find_all('a', href=True):
        output.append(link['href'])

    return output


def get_nonfiction_data(information_table):
    return [
        [
            td.a['href']
            if td.text in ['[1]', '[2]', '[3]']
            else "".join(td.stripped_strings)
            for td in row.find_all("td")
        ]
        for row in information_table.find_all("tr")[
            1:
        ]
    ]


def get_fiction_data(information_table):
    return [
        [
            get_all_fiction_mirrors(td)
            if td.find("ul", class_=['record_mirrors_compact'])
            else "".join(td.stripped_strings).split(' / ')[0].lower() if ' / ' in "".join(td.stripped_strings)
            else "".join(td.stripped_strings)
            for td in row.find_all("td")
        ]
        for row in information_table.find_all("tr")[1:]  # Skip row 0 as it is the headings row
    ]


class SearchRequest:

    def __init__(self, genre, query, search_type="title"):
        self.col_names = None
        self.genre = genre
        self.query = query
        self.search_type = search_type

        if len(self.query) <= 2:
            raise Exception("Query is too short")

    def get_fiction_search_page(self):
        if self.search_type.lower() == "title":
            search_url = f"https://libgen.rs/fiction/?q={urllib.parse.quote_plus(self.query)}&criteriatitle=&language=English&format="
        elif self.search_type.lower() == "author":
            search_url = f"http://gen.lib.rus.ec/fiction/?q={urllib.parse.quote_plus(self.query)}&column=author"
        search_page = requests.get(search_url)
        return search_page

    def get_non_fiction_search_page(self):
        if self.search_type.lower() == "title":
            search_url = f"http://gen.lib.rus.ec/search.php?req={urllib.parse.quote(self.query)}&column=title"
        elif self.search_type.lower() == "author":
            search_url = f"http://gen.lib.rus.ec/search.php?req={urllib.parse.quote(self.query)}&column=author"
        search_page = requests.get(search_url)
        return search_page

    def get_search_page(self):
        if self.genre == 'fiction':
            return self.get_fiction_search_page()
        else:
            return self.get_non_fiction_search_page()

    def set_columns(self, soup):
        if self.genre == 'fiction':
            table = soup.find('table', attrs={'class': 'catalog'})
            self.col_names = [th.text for th in table.find('thead').select('td')]
            i = self.col_names.index('File')
            self.col_names[i] = 'Extension'
        else:
            table = soup.find_all("table")[2]
            column_row = table.find_all('tr')[0].select('td')
            self.col_names = [b.text for b in column_row]
            mirror = self.col_names.index('Mirrors')
            self.col_names[mirror:mirror + 1] = 'Mirror_1', 'Mirror_2', 'Mirror_3'
            self.col_names = self.col_names

    def get_data(self, information_table):
        if self.genre == 'fiction':
            return get_fiction_data(information_table)
        else:
            return get_nonfiction_data(information_table)

    def aggregate_request_data(self):
        search_page = self.get_search_page()
        soup = BeautifulSoup(search_page.text, "lxml")
        strip_i_tag_from_soup(soup)
        information_table = soup.find_all("table")[genre_table_ints.get(self.genre)]
        self.set_columns(soup)
        raw_data = self.get_data(information_table)

        output_data = [dict(zip(self.col_names, row)) for row in raw_data]
        return output_data
