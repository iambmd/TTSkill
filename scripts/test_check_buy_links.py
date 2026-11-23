"""Regression tests for rubber purchase link verification."""
from __future__ import annotations

import unittest
from decimal import Decimal

from check_buy_links import check_amazon, product_url, reference_price

AMAZON_URL = "https://www.amazon.com/dp/B010234567"
AMAZON_LINK = {"store": "Amazon", "url": AMAZON_URL, "type": "amazon-other"}
PRODUCT = "DHS Hurricane 3 Neo"
REFERENCE = Decimal("40.00")


def amazon_page(price: str, title: str = "DHS Hurricane 3 Neo Table Tennis Rubber – Black") -> str:
    return f"""<span id="productTitle">{title}</span>
    <span class="a-price"><span class="a-offscreen">$10.00</span></span>
    <div id="corePrice_feature_div">
      <span class="a-price a-text-price"><span class="a-offscreen">$40.00</span></span>
      <span class="a-price"><span class="a-offscreen">{price}</span></span>
    </div>"""


class PurchaseLinksTest(unittest.TestCase):
    def test_threshold_is_strict_and_uses_current_offer(self):
        for price, status in [("$28.00", "OK"), ("$27.99", "SUSPECT"), ("", "UNVERIFIED")]:
            with self.subTest(price=price):
                result, _ = check_amazon(PRODUCT, AMAZON_LINK, amazon_page(price), AMAZON_URL, REFERENCE)
                self.assertEqual(result, status)

    def test_distinct_editions_and_redirects(self):
        for wrong_title in ["DHS Hurricane 3 Table Tennis Rubber", "DHS Hurricane 3 Neo Rubber - Provincial"]:
            with self.subTest(title=wrong_title):
                self.assertEqual(check_amazon(PRODUCT, AMAZON_LINK, amazon_page("$35.00", wrong_title), AMAZON_URL, REFERENCE)[0], "MISMATCH")
        self.assertEqual(check_amazon(PRODUCT, AMAZON_LINK, amazon_page("$35.00"), AMAZON_URL + "0", REFERENCE)[0], "BROKEN")
        self.assertFalse(product_url(AMAZON_URL + "?tag=affiliate-20", "Amazon", "amazon-other"))

    def test_selected_color_and_primary_offer(self):
        html = amazon_page("$31.00", "DHS Sports Hurricane 9 Table Tennis Rubber")
        html += '<div id="buybox"><span class="a-price"><span class="a-offscreen">$18.00</span></span></div>'
        html += '<table><tr><th class="prodDetSectionEntry">Color</th><td>Pink</td></tr></table>'
        self.assertEqual(check_amazon("DHS Hurricane 9 Pink", AMAZON_LINK, html, AMAZON_URL, REFERENCE)[0], "OK")
        self.assertEqual(check_amazon("DHS Hurricane 9 Violet", AMAZON_LINK, html, AMAZON_URL, REFERENCE)[0], "MISMATCH")

    def test_reference_prefers_catalog_then_exact_us_retail_listing(self):
        palace = {"store": "Paddle Palace", "url": "https://www.paddlepalace.com/products/example", "type": "retailer"}
        def load(url: str) -> tuple[str, str, str]:
            return "OK", url, ('<h1>DHS Hurricane 3 Neo</h1>'
                               '<meta property="product:price:currency" content="USD">'
                               '<meta property="product:price:amount" content="45.99">')

        self.assertEqual(reference_price(PRODUCT, [palace], {PRODUCT: REFERENCE}, load), REFERENCE)
        self.assertEqual(reference_price(PRODUCT, [palace], {}, load), Decimal("45.99"))
        self.assertIsNone(reference_price("DHS Hurricane 3", [palace], {}, load))
