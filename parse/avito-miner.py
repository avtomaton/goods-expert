#!/usr/bin/env python

# __author__ = 'avtomaton'

from lxml import html
from urllib2 import urlopen
from pandas import DataFrame
import sqlite3


host_url = 'https://www.avito.ru'
page_url = '/moskva/nastolnye_kompyutery'
page_params = 'view=list'
list_div_name = 'js-catalog_after-ads'

list_pages = 2


class AvitoAd:

    def __init__(self, record_div):
        self.title_div = "title"
        self.date_div = "date"  # contained in title_div!
        self.price_div = "price"
        self.photo_div = "photo"
        self.address_div = "data"

        self.price2_div = "p_i_price"
        self.seller_div = ["seller", "name"]
        self.desc_block = "div#desc_text"
        self.desc_block2 = "div.description-content"

        self.id = None
        self.title = None
        self.link = None
        self.price = None
        self.discount_from = None
        self.location = None
        self.date = None
        self.seller = None
        self.seller_type = None
        self.text = None

        self.parse_from_list(record_div)

    # parse from large list (grab only main info and permalink
    def parse_from_list(self, record_div):

        self.id = record_div.get('id')
        title = record_div.find_class(self.title_div)
        if len(title) != 1:
            raise RuntimeError("can't retrieve record title")
        links = [l for l in title[0].iterlinks()]
        if len(links) != 1:
            raise RuntimeError("can't retrieve record link")
        date = title[0].find_class(self.date_div)
        if len(date) != 1:
            raise RuntimeError("can't retrieve record date")

        # one link is (element, attribute, link, pos)
        self.title = links[0][0].text.strip()
        self.link = links[0][2].strip()
        self.date = date[0].text.strip()

        price = record_div.find_class(self.price_div)
        if len(price) != 1:
            raise RuntimeError("can't retrieve record price")
        price = price[0][0].text.strip()
        self.price = price[:-3]  # drop currency

        location = record_div.find_class(self.address_div)
        if len(location) != 1:
            raise RuntimeError("can't retrieve record location")
        self.location = location[0].text_content().strip()

        self.parse_link()

    # parse ad permalink (grab seller, description and price)
    def parse_link(self):
        page = html.parse(urlopen(host_url + self.link))
        page = page.getroot()
        price = page.find_class(self.price2_div)

        if len(price) != 1:
            raise RuntimeError("ad page: can't retrieve price")

        price = price[0].text_content().strip()
        price = price[:-5]  # drop currency
        if price != self.price:
            self.discount_from = self.price
            print "'" + self.title + "' DISCOUNT: " + self.price + " -> " + price
            self.price = price

        seller = page.get_element_by_id(self.seller_div[0])
        seller_type = seller.cssselect('c-2')
        seller = seller.xpath('.//strong[@itemprop="' + self.seller_div[1] + '"]/text()')
        # print seller[0].__class__
        if len(seller) != 1:
            raise RuntimeError("ad page: can't retrieve seller name")
        self.seller = seller[0].strip()
        if seller_type:
            self.seller_type = seller_type
        else:
            self.seller_type = 'private'

        print self.title + ' === ' + self.seller + ' === ' + self.price

        desc = page.cssselect(self.desc_block)
        if len(desc) != 1:  # try another name (shop)
            desc = page.cssselect(self.desc_block2)
        if len(desc) != 1:
            raise RuntimeError("ad page: can't retrieve description")
        self.text = desc[0].text_content().strip()


def explore_records(url, wanted_div, cursor, conn):

    page = html.parse(urlopen(url))
    list_div = page.getroot().find_class(wanted_div)
    if len(list_div) != 1:
        raise RuntimeError("can't retrieve element with records list (" + wanted_div + ")")

    ads = []
    lst = list_div[0].getchildren()
    repeat = 0
    for el in lst:
        cur = AvitoAd(el)
        cursor.execute('SELECT id FROM ads WHERE id=?', (cur.id,))
        if cursor.fetchone() is not None:
            repeat += 1
            continue
        else:
            repeat = 0
        if repeat > 5:
            break
        cursor.execute('INSERT INTO ads VALUES (?, ?, ?, ?, ?, ?)',
                       (cur.id, cur.title, cur.seller, cur.date, cur.price, cur.text))
        conn.commit()
        ads.append(cur)

    print "collected %d ads" % (len(ads))


def scan_all():
    conn = sqlite3.connect('avito-parser.db')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS ads(id text, title text,'
                   'seller text, date text, price text, desc text)')
    conn.commit()
    for p in range(list_pages):
        if p == 0:
            full_addr = host_url + page_url + '?' + page_params
        else:
            full_addr = host_url + page_url + '?' + 'p=' + str(p + 1) + '&' + page_params
        explore_records(full_addr, list_div_name, cursor, conn)

    conn.close()


if __name__ == '__main__':
    scan_all()
