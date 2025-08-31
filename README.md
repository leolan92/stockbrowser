// Updated on 2025-08-31

## Project functions
1. Creating a html dashboard for TW stocks, exchange rates and metals price (TODO) for daily review.
2. Able to add TW stocks, exchange rate into TWD and metal prices into TWD (TODO) by user.
3. Able to add event by date by user.

## Project overview (Figure)
<img width="1902" height="974" alt="image" src="https://github.com/user-attachments/assets/08aa95fe-8b0d-4abc-b161-88b25e15ffa3" />

## Project usage
1. Entering `python -m core.src.web` at project home.
2. Open the generated URL (ex: `http://127.0.0.1:5001`) on browser.
3. From browser, user could add TW stock id (ex: `2330`) or exchange rate (ex: `USD` or `EUR`) and press `更新圖表` to update the charts.
4. From browser, user could add event by date and comment into charts.

## Project structure
```
.
├── chart.html
├── chart.png
├── core
│   ├── __init__.py
│   ├── backup
│   │   └── web.py
│   └── src
│       ├── __init__.py
│       ├── db.py
│       ├── log.py
│       └── web.py
├── db.sqlite
├── static
├── structure.txt
└── templates
    ├── bk_index_bk.html
    └── index.html

6 directories, 12 files
```
