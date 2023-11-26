#!/usr/bin/env python3
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium import webdriver
from pyquery import PyQuery as pq
from os.path import exists
from sys import argv, stderr
import sys
sys.stdout.reconfigure(encoding='shift-jis')

LN_DISABLE = False
GLOBAL_BPM = 1
LOCAL_BPM = 1

CSS_LEFT_TO_CHANNEL = {
    '0px': '16',
    '37px': '11',
    '51px': '12',
    '65px': '13',
    '79px': '14',
    '93px': '15',
    '107px': '18',
    '121px': '19',
    '03' : '03',
    '08' : '08'
}

GLOBAL_BPM_LIST = {}

def top_to_pos(t_height, top_px):
    pos = abs(int(top_px.replace('px', '')) - t_height) - 5
    if pos == 10:
        pos = 11
    if pos == 42:
        pos = 43
    if pos == 74:
        pos = 75
    if pos == 106:
        pos = 107
    print(pos, file=stderr)
    return pos


def compress_notes(notes):
    return notes
    """
    for skip in map(lambda i: 2 ** i, range(7, 0, -1)):  # 128..2
        masked_notes = map(lambda ib: (
            ib[0] % skip != 0) and ib[1], enumerate(notes))
        if not any(masked_notes):
            return notes[::skip]
    return notes
    """


def get_channels(table):
    channels = {}
    t_height = int(table.attr['height'])
    deferring_lns = []
    global LOCAL_BPM

    for channel in CSS_LEFT_TO_CHANNEL.values():
        channels[channel] = [False] * t_height
    for bpm in table.find('span'):
        style = pq(bpm).attr['style']
        bpmt = pq(bpm).text() #text
        print('bpm : ', bpmt, file=stderr)
        try:
            zindex, left, top = tuple(map(lambda s: s.split(':')[1].strip(), style.split(';')[:3]))
            print('success ',top, style, file=stderr)
        except Exception as e:
            print('exception ',style, file=stderr)  # BPM change?
            continue
        if int(bpmt) > 255 : 
            pos, channel = top_to_pos(t_height, str(int(top.replace('px', ''))+2)+'px'), CSS_LEFT_TO_CHANNEL['08']
            try:
                channels[channel][pos] = GLOBAL_BPM_LIST[str(bpmt)+'_'+str(LOCAL_BPM)]
                print('localbpmt ' , GLOBAL_BPM_LIST[str(bpmt)+'_'+str(LOCAL_BPM)],file=stderr)
                LOCAL_BPM = LOCAL_BPM + 1
            except Exception as e:
                print('exc e ',channel, pos, style, file=stderr)  # Unsupported?
                if pos > t_height - 1:
                    pos = t_height - 1
                elif pos < 0:
                    pos = 0
                channels[channel][pos] = GLOBAL_BPM_LIST[str(bpmt)+'_'+str(LOCAL_BPM)]
                print('localbpmt ' , GLOBAL_BPM_LIST[str(bpmt)+'_'+str(LOCAL_BPM)],file=stderr)
                LOCAL_BPM = LOCAL_BPM + 1
        else:
            pos, channel = top_to_pos(t_height, str(int(round(float(top.replace('px', ''))))+2)+'px'), CSS_LEFT_TO_CHANNEL['03'] #bpm is 2px upper
            try:
                channels[channel][pos] = bpmt
            except Exception as e:
                print('exc e ',channel, pos, style, file=stderr)  # Unsupported?
                if pos > t_height - 1:
                    pos = t_height - 1
                elif pos < 0:
                    pos = 0
                channels[channel][pos] = bpmt
    for note in table.find('img'):
        style = pq(note).attr['style']
        if style is None or 'height:' in style:  # LN
            if LN_DISABLE:
                print('Ignoring LN', file=stderr)
                continue
            try:
                top, left, height = tuple(map(lambda s: s.split(
                    ':')[1].strip(), style.split(';')[:3]))
            except:
                print('Padding?', pq(note), file=stderr)
                continue
            t_i, l_i, h_i = map(lambda s: int(
                s.replace('px', '')), [top, left, height])
            pos = top_to_pos(t_height, str((t_i + h_i) - 4))
            key = str(l_i - 2 if l_i == 2 else l_i - 1) + 'px'
            channel = str(int(CSS_LEFT_TO_CHANNEL[key]) + 40) # LN Channel

            if channel not in channels:
                channels[channel] = [False] * t_height
            channels[channel][pos] = True
            end_pos = pos + h_i
            # print('LN', channel, pos, file=stderr)

            deferring_lns.append((channel, end_pos))
            continue
        try:
            top, left = tuple(map(lambda s: s.split(
                ':')[1].strip(), style.split(';')[:2]))
        except Exception as e:
            print(style, file=stderr)  # BPM change?
            continue
        pos, channel = top_to_pos(t_height, top), CSS_LEFT_TO_CHANNEL[left]
        try:
            channels[channel][pos] = True
        except Exception as e:
            print(channel, pos, style, file=stderr)  # Unsupported?
            if pos > t_height - 1:
                pos = t_height - 1
            elif pos < 0:
                pos = 0
            channels[channel][pos] = True

    measure = t_height / 128

    if measure == 1:
        compressed_channels = {}
        for channel, notes in channels.items():
            compressed_channels[channel] = compress_notes(notes)
    else:
        compressed_channels = channels
    if measure != 1 and measure != 1 / 16:  # End trim
        compressed_channels['02'] = measure
    return compressed_channels, deferring_lns, t_height


def get_sections(doc):
    sections = []
    deferring_lns_merge = []
    section_t_height = {}
    forbidden_secnum = 0
    for table in doc.find('table[cellpadding="0"]'):
        table = pq(table)
        try:
            section_num = int(table.find('th[bgcolor="gray"]').text())
            forbidden_secnum = section_num
        except:
            section_num = forbidden_secnum + 1
            forbidden_secnum += 1
        print('Section', section_num, file=stderr)
        channels, deferring_lns, t_height = get_channels(table)
        section_t_height[section_num] = t_height
        sections.append([section_num, channels])
        for d in deferring_lns:
            deferring_lns_merge.append(
                (d[0], (section_num + (d[1] // t_height)), d[1] % t_height))
    for i, section in enumerate(sections):
        if section[0] == -1:
            new_section_num = max(sections, key=lambda s: s[0])[0] + 1
            print(
                'Section {} -> {}'.format(section[0], new_section_num), file=stderr)
            section[0] = new_section_num
            section_t_height[new_section_num] = section_t_height[-1]
    sections.sort(key=lambda s: s[0])
    #print(sections, file=stderr)
    has_end = set()
    print(deferring_lns_merge, file=stderr)
    for d in deferring_lns_merge:
        if d[2] != 0:
            has_end.add((d[0], d[1],))
        elif (d[2] == 0 and not(d[0],d[1]+1,) in has_end):
            #trace back to initial end
            i=1
            add = False
            while True:
                if((d[0],d[1]+i,d[1]+i+1) in has_end):
                    i+=1
                    continue
                elif((d[0],d[1]+i,d[1]+i) in has_end):
                    has_end.add((d[0], d[1], d[1]+1))
                    break
                else:
                    has_end.add((d[0], d[1],d[1]))
                    break
            
    offset = sections[0][0] - 1
    print(has_end, file=stderr)
    for d in deferring_lns_merge:
        sec_num = d[1] - 1 - offset
        channels = sections[sec_num][1]
        if d[0] not in channels:
            channels[d[0]] = [False] * section_t_height[section_num]
        if (d[2] == 0 and (d[0], d[1]) in has_end) or (d[2]==0 and (d[0], d[1], d[1]+1) in has_end):
            print('Will not append LN end at', d, file=stderr)
            sections[sec_num][1][d[0]][d[2]] = False
        else:
            sections[sec_num][1][d[0]][d[2]] = True
        sections[sec_num][1][str(int(d[0]) - 40)][d[2]] = False
    return sections

def get_driver():
    for trial in [
        ["c", "/usr/bin/chromium"],
        ["c", "/usr/bin/chrome"],
        ["c", None],
        ["f", "/usr/bin/firefox"],
        ["f", None]
    ]:
        try:
            options = ChromeOptions() if trial[0] == "c" else FirefoxOptions() 
            options.add_argument("--headless" if trial[0] == "c" else "-headless")
            if trial[0] == "c":
                options.binary_location = trial[1]
            b = webdriver.Chrome(options=options) if trial[0] == "c" else webdriver.Firefox(firefox_binary=trial[1], options=options)
            return b
        except Exception as e:
            print(e, file=stderr)

if __name__ == '__main__':
    b = get_driver()
    b.get(argv[1])
    doc = pq(b.page_source)
    headers = {
        '#PLAYER': '1',
        '#RANK': '3',
        '#DIFFICULTY': '4',
        '#STAGEFILE': '',
        '#GENRE': b.execute_script('return genre'),
        '#TITLE': b.execute_script('return title'),
        '#ARTIST': b.execute_script('return artist'),
        '#BPM': b.execute_script('return bpm'),
        '#PLAYLEVEL': '12',
        '#WAV02': 'out.wav',
    }
    button = 0
    for table in doc.find('table[cellpadding="0"]'):
        for bpm in pq(table).find('span'):
            bpmt = (pq(bpm).text())
            if int(bpmt) > 255:
                print('#BPM'+(str(f'{GLOBAL_BPM:02d}')), bpmt,file=stderr)
                headers['#BPM'+(str(f'{GLOBAL_BPM:02d}'))] = bpmt
                GLOBAL_BPM_LIST[str(bpmt)+'_'+str(GLOBAL_BPM)] = str(format(GLOBAL_BPM, '02X'))
                print('gbpm '+GLOBAL_BPM_LIST[str(bpmt)+'_'+str(GLOBAL_BPM)], file=stderr)
                GLOBAL_BPM = GLOBAL_BPM + 1
            if button == 0:
                headers['#BPM'] = bpmt
                button = 1

    print('*---------------------- HEADER FIELD')
    for k, v in headers.items():
        print(k, v)
    print('\n*---------------------- MAIN DATA FIELD\n#00101:02\n')
    sections = get_sections(doc)
    for section in sections:
        section_num, channels = section
        for channel, notes in channels.items():
            if isinstance(notes, list):
                if not any(notes):
                    continue
                if channel == '03' or channel == '08':
                    data = "".join(list(map(lambda b: str(format(int(b),'02X')) if b else '00', notes)))
                else :
                    data = "".join(list(map(lambda b: 'AA' if b else '00', notes)))
            else:
                data = notes
            print('#{:03d}{}:{}'.format(section_num, channel, data))
        print()
