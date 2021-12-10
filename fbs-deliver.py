import json
import os
import datetime
import requests
import math
from PyPDF2 import PdfFileMerger


url_api = 'https://api-seller.ozon.ru'
url_get_deliver = url_api + '/v2/posting/fbs/list'

client_id = os.environ['CLIENT_ID']
api_key = os.environ['API_KEY']

colors = {
    '00': 'Чёрный',
    '01': 'Белый',
    '02': 'Т-серый',
    '03': 'Св-серый',
    '04': 'Красный',
    '05': 'Бордовый',
    '06': 'Оранжевый',
    '07': 'Жёлтый',
    '08': 'Зелёный',
    '09': 'Т-синий',
    '10': 'Васильковый',
    '11': 'Голубой',
    '12': 'Хаки'
}
sizes = {
    '48': 'S',
    '50': 'M',
    '52': 'L',
    '54': 'XL',
    '56': 'XXL'
}
headers = {
    'Content-Type': 'application/json; charset=utf-8',
    'Client-Id': client_id,
    'Api-Key': api_key
}

payload = {
    'dir': 'asc',
    'filter': {'status': 'awaiting_deliver'},
    'limit': 50,
    'offset': 0
}


def get_date(d: str):
    d = d.split('T')[0]
    d = d.split('-')
    return f'{d[2]}.{d[1]}.{d[0]}'


delivers = []


def get_deliver():
    data = requests.post(url_get_deliver, headers=headers, data=json.dumps(payload)).json()
    delivers.extend(data['result'])

    if len(data['result']) == 50:
        payload['offset'] += 50
        get_deliver()
    else:
        return


print('Получение новых отправлений...')
get_deliver()

orders = {}

for order in delivers:
    date = get_date(order['shipment_date'])
    if not date in orders: orders[date] = []
    orders[date].append(order)


out_data = ''
total = {}
cur_date = None

for date_k, order_v in orders.items():
    quantity_orders = 0
    quantity_shirts = 0
    out_data = ''

    print('Производится улучшеная сортировка ' + date_k)
    orders_sorted_by_size = sorted(order_v, key=lambda x: x['products'][0]['offer_id'][-2:])
    orders_sorted_by_density = sorted(orders_sorted_by_size, key=lambda x: x['products'][0]['offer_id'][-7:-4])
    orders_sorted_by_color = sorted(orders_sorted_by_density, key=lambda x: x['products'][0]['offer_id'][-4:-2])
    orders_sorted = sorted(orders_sorted_by_color, key=lambda x: len(x['products']))

    postings = []

    print('Формирование листов подбора ' + date_k)

    for order in orders_sorted:
        if order['products'][0]['offer_id'][:2] in ['01', '11', '21', '31', '41', 'u0', 'u1', 'u2', 'u3', 'u4']:
            date = date_k
            quantity_orders += 1
            if date != cur_date:
                cur_date = date
                out_data += f'''                    {cur_date}
'''
            post = order['posting_number']
            postings.append(post)

            out_data += f'''-------------------------
{post}
'''

            for prod in order['products']:
                id = prod['offer_id']
                if id[0] == 'u': id = id[1:]
                density = id[1:4]
                color = colors[id[4:6]]
                size = id[6:] + '-' + sizes[id[6:]]
                quantity = prod['quantity']
                quantity_shirts += quantity

                if not cur_date in total: total[cur_date] = {}
                if not density in total[cur_date]: total[cur_date][density] = {}
                if not color in total[cur_date][density]:
                    total[cur_date][density][color] = {}
                if not size in total[cur_date][density][color]:
                    total[cur_date][density][color][size] = 0

                total[cur_date][density][color][size] += quantity

                out_data += f'''{color}/{size}({density})-{quantity}шт.
'''
    out_data += f'''====================================================
    Количество футболок - {quantity_shirts}
    Количество отправлений - {quantity_orders}'''
    with open(date_k + '_Podbor.txt', 'w+') as f:
        f.write(out_data)

    if date_k == datetime.date.today().strftime('%d.%m.%Y'):
        url_get_labels = url_api + '/v2/posting/fbs/package-label'
        merger = PdfFileMerger()
        i = 0
        parts = math.ceil(len(postings) / 20)
        files = []

        print('Получение этикеток отправленй на ' + date_k)
        while len(postings) > 0:
            i += 1

            print(str(i) + ' часть из ' + str(parts) + ' ...')
            labels = requests.post(url_get_labels, headers=headers, data=json.dumps({'posting_number': postings[:20]}))
            if labels.status_code == 200:
                with open(str(i) + 'temp.pdf', 'wb+') as f:
                    f.write(labels.content)

                f = open(str(i) + 'temp.pdf', 'rb')
                merger.append(f)
                files.append(f)
                postings = postings[20:]

        with open(date_k + '_Marks.pdf', 'wb+') as f:
            merger.write(f)

        for f in files:
            f.close()

        while i > 0:
            os.remove(str(i) + 'temp.pdf')
            i -= 1

        print('Этикетки получены, формирование листов подбора на другие дни...')


total_all = 0
for date, d in total.items():
    total_all = 0
    out_data = f'''{date}:'''
    for density, c in reversed(d.items()):
        out_data += f'''
    -----------------------------------------------
    {density}:'''
        for color, s in c.items():
            out_data += f'''
            {color}:'''
            for size, q in s.items():
                total_all += q
                out_data += f'''
                {size}: {q}шт.'''
    
    out_data += f'''
    
    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
        Всего на {date} отгрузить: {total_all}шт.
    /////////////////////////////////////////////////'''
    with open(date + '_Total.txt', 'w+') as f:
        f.write(out_data)

input('Всё готово! Нажмите любую клавишу!\n\nЭтого озона рот...\n...ственник)')
