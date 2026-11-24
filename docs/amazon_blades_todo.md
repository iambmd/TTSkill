# Amazon blade links: to check in a browser

**Status:** no Amazon blade links are in the app yet. `shared/blade-buy-links.json` has none, and `scripts/check_buy_links.py --blades` never fetches Amazon (Amazon answers scripted requests with a bot check, so these are checked by a person).

The list below is the blades most worth doing first: the most-rated blades on RevSpin (a stand-in for popularity), brand by brand. "Verified US stores already" is what the app shows today; the Amazon link would sit next to those.

## How to check one

1. Open the brand's **official Amazon storefront** in a normal browser and go to its Blades tab:
   - Butterfly: [Butterfly storefront (Rubber tab used for the rubbers)](https://www.amazon.com/stores/page/4325729E-0DDF-4FA8-A737-27BCC08A2070): open its Blades tab
   - JOOLA: [JOOLA North America storefront](https://www.amazon.com/stores/JOOLANorthAmerica/page/54862E6E-D0CD-466E-BBDD-72DB8E617060)
   - STIGA: [STIGA storefront](https://www.amazon.com/stores/STIGA/page/BC1F59CB-CE5D-44D6-BFC1-F7EF88B33AE4)
2. The listing's title must name the **exact blade** in the first column (the same rule as the rubbers: "Viscaria", "Viscaria Super ALC" and "Viscaria CS" are three different blades). Skip it if the model, edition or handle isn't the one listed.
3. Copy the 10-character ASIN from the address (`amazon.com/dp/B0XXXXXXXX`). Do not copy `tag=`, `ref=` or any other parameter: the app adds the affiliate tag itself from `NEXT_PUBLIC_AMAZON_TAG`.
4. Note the price shown and who sells it ("Sold by" / "Ships from").
   - On the brand's **official storefront**, sold by the brand: type `amazon-official`.
   - Any **other seller**: type `amazon-other`. It is labelled "Amazon (other seller)" and always sorted last. Leave it out if its price is **more than 30% below** the reference price in the table (a sign of a counterfeit or a different item). The check is `price >= 0.70 x reference`.
5. Add the entry to `shared/blade-buy-links.json` under the exact RevSpin name:

   ```json
   "Butterfly Viscaria": [
     {"store": "Amazon", "url": "https://www.amazon.com/dp/B0XXXXXXXX", "type": "amazon-official"}
   ]
   ```

6. Run `python3 scripts/check_buy_links.py --blades --show-ok`. Amazon rows show as UNVERIFIED on purpose (never fetched); the other rows must stay OK. Then `cd frontend && npm test`, which checks the file's shape. (`frontend/test/blades.test.ts` currently asserts the catalogue has no Amazon link: change that expectation when you add the first one.)

## Butterfly (official storefront)

Butterfly makes the most-rated blades. Several are discontinued: if the Blades tab doesn't list one, leave it blank.

| # | Blade (RevSpin name) | Ref. price | RevSpin ratings | Score | Handles known | Verified US stores already | Amazon ASIN | Amazon price | Seller / notes |
| ---: | --- | ---: | ---: | ---: | --- | --- | --- | --- | --- |
| 1 | Butterfly Viscaria | $185 | 179 | 9.4 | FL/ST | Paddle Palace, TableTennisStore |  |  |  |
| 2 | Butterfly Timo Boll ALC | $185 | 159 | 9.4 | FL/ST/AN/CS | Paddle Palace, eTableTennis |  |  |  |
| 3 | Butterfly Timo Boll Spirit | $135 | 124 | 9.3 | FL | Paddle Palace, eTableTennis |  |  |  |
| 4 | Butterfly Petr Korbel | $70 | 120 | 9.0 | FL/ST | Paddle Palace, TableTennisStore, eTableTennis |  |  |  |
| 5 | Butterfly Michael Maze | $320 | 94 | 9.2 | ? | none yet |  |  |  |
| 6 | Butterfly Primorac | $110 | 89 | 8.6 | FL | Paddle Palace, eTableTennis |  |  |  |
| 7 | Butterfly Primorac Carbon TAMCA 5000 | $116 | 73 | 9.0 | ? | none yet |  |  |  |
| 8 | Butterfly Zhang Jike | $230 | 70 | 7.6 | ? | none yet |  |  |  |
| 9 | Butterfly Innerforce ZLC | $200 | 68 | 9.4 | ? | none yet |  |  |  |
| 10 | Butterfly Amultart ZL Carbon | $500 | 61 | 9.5 | FL/ST | TableTennisStore, eTableTennis |  |  |  |
| 11 | Butterfly Sardius | $146 | 61 | 8.8 | FL | eTableTennis |  |  |  |
| 12 | Butterfly Balsa Carbo X5 | $70 | 59 | 8.8 | ? | eTableTennis |  |  |  |
| 13 | Butterfly Innerforce Layer ZLC | $220 | 59 | 9.3 | FL/ST/AN/CS | Paddle Palace, TableTennisStore, eTableTennis |  |  |  |
| 14 | Butterfly Zhang Jike ALC | $214 | 59 | 9.5 | FL/ST/AN | TableTennisStore |  |  |  |
| 15 | Butterfly Timo Boll ZLF | $180 | 55 | 9.5 | ST/CS | TableTennisStore, eTableTennis |  |  |  |
| 16 | Butterfly Freitas ALC | $185 | 52 | 8.6 | FL/ST/AN | eTableTennis |  |  |  |
| 17 | Butterfly Innerforce Layer ALC | $195 | 51 | 9.3 | FL/ST/AN/CS | Paddle Palace, TableTennisStore, eTableTennis |  |  |  |
| 18 | Butterfly Schlager Carbon | $400 | 51 | 9.0 | ? | none yet |  |  |  |
| 19 | Butterfly Timo Boll ZLC | $215 | 51 | 9.3 | FL/ST/AN/CS | Paddle Palace, TableTennisStore, eTableTennis |  |  |  |
| 20 | Butterfly Zhang Jike Super ZLC | $350 | 49 | 9.4 | ? | none yet |  |  |  |
| 21 | Butterfly Liu Shiwen | $245 | 48 | 9.6 | ? | none yet |  |  |  |
| 22 | Butterfly Garaydia ZLC | $220 | 45 | 9.0 | ? | eTableTennis |  |  |  |
| 23 | Butterfly Marcos Freitas ALC | $185 | 45 | 9.5 | ? | none yet |  |  |  |
| 24 | Butterfly Jun Mizutani | $230 | 44 | 9.4 | ? | none yet |  |  |  |
| 25 | Butterfly Harimoto Innerforce Super ZLC | $350 | 43 | 9.6 | FL/ST/AN/CS | Paddle Palace, TableTennisStore, eTableTennis |  |  |  |

## JOOLA (official storefront)



| # | Blade (RevSpin name) | Ref. price | RevSpin ratings | Score | Handles known | Verified US stores already | Amazon ASIN | Amazon price | Seller / notes |
| ---: | --- | ---: | ---: | ---: | --- | --- | --- | --- | --- |
| 1 | JOOLA Rossi Emotion | $100 | 46 | 9.3 | ? | none yet |  |  |  |
| 2 | JOOLA Energon Super PBO-c | $190 | 43 | 9.4 | ? | none yet |  |  |  |
| 3 | JOOLA Kool | $190 | 33 | 9.4 | ? | none yet |  |  |  |
| 4 | JOOLA MC1 | $99 | 31 | 9.3 | ? | none yet |  |  |  |
| 5 | JOOLA Fever | $140 | 25 | 9.3 | ? | none yet |  |  |  |
| 6 | JOOLA Viva | $21 | 23 | 9.0 | ? | none yet |  |  |  |
| 7 | JOOLA Aruna OFF | $140 | 20 | 9.4 | ? | none yet |  |  |  |
| 8 | JOOLA Vyzaryz Hybrid | $250 | 20 | 9.3 | FL/ST/PH | JOOLA USA |  |  |  |
| 9 | JOOLA Vyzaryz Trinity | $275 | 20 | 9.6 | PH | JOOLA USA |  |  |  |
| 10 | JOOLA Bomb Extrem MCD | $185 | 19 | 9.0 | ? | none yet |  |  |  |
| 11 | JOOLA Chen Weixing | $50 | 19 | 8.7 | ? | none yet |  |  |  |
| 12 | JOOLA Flame Extreme | $120 | 19 | 9.2 | ? | none yet |  |  |  |
| 13 | JOOLA Nobilis PBO-c | $200 | 19 | 9.2 | PH | JOOLA USA |  |  |  |
| 14 | JOOLA Vyzaryz Freeze | $200 | 19 | 8.8 | FL/ST | JOOLA USA |  |  |  |
| 15 | JOOLA Wing Passion Extreme | $110 | 15 | 9.3 | ? | none yet |  |  |  |

## STIGA (official storefront)



| # | Blade (RevSpin name) | Ref. price | RevSpin ratings | Score | Handles known | Verified US stores already | Amazon ASIN | Amazon price | Seller / notes |
| ---: | --- | ---: | ---: | ---: | --- | --- | --- | --- | --- |
| 1 | Stiga Infinity VPS V Diamond Touch | $70 | 88 | 9.1 | CS | TableTennisStore |  |  |  |
| 2 | Stiga Allround Classic | $62 | 68 | 8.3 | FL/CS/PH | Go Table Tennis, Paddle Palace, TableTennisStore |  |  |  |
| 3 | Stiga Hybrid Wood NCT | $108 | 66 | 9.6 | ? | none yet |  |  |  |
| 4 | Stiga Clipper | $70 | 55 | 9.2 | ? | none yet |  |  |  |
| 5 | Stiga Rosewood NCT V | $115 | 50 | 9.3 | ? | none yet |  |  |  |
| 6 | Stiga Offensive Classic (OC) | $48 | 46 | 8.4 | ? | none yet |  |  |  |
| 7 | Stiga Dynasty Carbon Xu Xin Edition | $350 | 44 | 9.6 | ? | Paddle Palace |  |  |  |
| 8 | Stiga Rosewood NCT VII | $100 | 38 | 9.5 | CS | TableTennisStore |  |  |  |
| 9 | Stiga Clipper CR (WRB) | $77 | 37 | 9.1 | ? | none yet |  |  |  |
| 10 | Stiga Clipper CC | $150 | 36 | 9.5 | ? | none yet |  |  |  |
| 11 | Stiga Ebenholz NCT V (5) | $137 | 34 | 9.2 | ? | none yet |  |  |  |
| 12 | Stiga Allround NCT | $52 | 31 | 9.2 | ? | none yet |  |  |  |
| 13 | Stiga Ebenholz NCT VII (7) | $135 | 29 | 9.3 | ? | none yet |  |  |  |
| 14 | Stiga Allround Classic WRB | $43 | 27 | 8.5 | ? | none yet |  |  |  |
| 15 | Stiga Carbonado 190 | $120 | 27 | 9.4 | ? | none yet |  |  |  |

## Other brands (check whether the brand has an official Amazon store first)

For these, an Amazon listing is usually another seller (`amazon-other`) unless the brand runs its own storefront.

| # | Blade (RevSpin name) | Ref. price | RevSpin ratings | Score | Handles known | Verified US stores already | Amazon ASIN | Amazon price | Seller / notes |
| ---: | --- | ---: | ---: | ---: | --- | --- | --- | --- | --- |
| 1 | DHS Power-G PG7 | $40 | 155 | 9.1 | ? | none yet |  |  |  |
| 2 | Tibhar Stratus Power Wood | $40 | 146 | 9.4 | FL/ST/AN | TableTennisStore, Paddle Palace |  |  |  |
| 3 | Nittaku Acoustic | $165 | 97 | 9.6 | FL/ST/PH | Go Table Tennis, Paddle Palace |  |  |  |
| 4 | DHS Hurricane 301 | $76 | 93 | 9.5 | CS/PH | Paddle Palace, DHS Sports USA, TableTennisStore |  |  |  |
| 5 | Yasaka Ma Lin Extra Offensive | $40 | 89 | 9.0 | ST | Go Table Tennis, Paddle Palace |  |  |  |
| 6 | DHS Hurricane Long 5 | $190 | 87 | 9.5 | PH | Paddle Palace, DHS Sports USA |  |  |  |
| 7 | Donic Waldner Senso Carbon | $50 | 87 | 9.1 | ? | none yet |  |  |  |
| 8 | Xiom Zetro Quad | $140 | 78 | 9.4 | ? | none yet |  |  |  |
| 9 | Nittaku Barwell Fleet | $204 | 67 | 9.4 | ? | none yet |  |  |  |
| 10 | Yasaka Sweden Extra | $43 | 67 | 9.0 | FL/ST/AN | Go Table Tennis |  |  |  |
| 11 | Andro Treiber Z | $125 | 65 | 9.4 | ? | none yet |  |  |  |
| 12 | Xiom Stradivarius | $105 | 65 | 9.0 | ? | none yet |  |  |  |
| 13 | DHS Hurricane Long 3 | $250 | 63 | 9.5 | ? | DHS Sports USA |  |  |  |
| 14 | Donic Waldner OFF World Champion 89 | $75 | 58 | 9.5 | ? | Paddle Palace |  |  |  |
| 15 | Yasaka Dynamix 17 | $73 | 56 | 9.6 | ? | none yet |  |  |  |
