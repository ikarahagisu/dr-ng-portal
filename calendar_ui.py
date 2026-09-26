import streamlit as st
import pandas as pd
import io

def _read_csv_any_encoding(file_bytes):
    """
    Shift-JIS / UTF-8 BOM / UTF-8 / latin-1 の順に試してDataFrameを返す。
    io.BytesIO はread後にポインタが末尾へ移動するため、
    エンコーディングごとに必ず新しいインスタンスを生成する。
    latin-1 は任意の1バイト列を読めるため実質フォールバックとして機能する。
    """
    for encoding in ('cp932', 'shift_jis', 'utf-8-sig', 'utf-8', 'latin-1'):
        try:
            return pd.read_csv(io.BytesIO(file_bytes), encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("CSVのエンコーディングを判定できませんでした。")

def normalize_shift_names(df):
    """以前のCSVの枠名・上限列・希望枠を現在の名称へ変換する。"""
    aliases = {"宿直A": "A宿直", "宿直B": "B宿直", "A当直": "A宿直", "B当直": "B宿直", "日直A": "A日直", "日直B": "B日直"}
    for old, new in aliases.items():
        for suffix in ("", "上限"):
            old_col, new_col = old + suffix, new + suffix
            if old_col not in df.columns:
                continue
            if new_col not in df.columns:
                df = df.rename(columns={old_col: new_col})
            else:
                blank = df[new_col].fillna("").astype(str).str.strip().eq("")
                df.loc[blank, new_col] = df.loc[blank, old_col]
                df = df.drop(columns=[old_col])
    request_col = "希望日(半角カンマ区切り)"
    if request_col in df.columns:
        def normalize_request(value):
            if not isinstance(value, str):
                return value
            for old, new in aliases.items():
                value = value.replace(old, new)
            return value
        df[request_col] = df[request_col].map(normalize_request)
    return df

def parse_staff_csv(file_bytes):
    df = normalize_shift_names(_read_csv_any_encoding(file_bytes))
    # 旧CSVの列名も受け付け、画面・出力CSVでは新名称に統一する。
    weekday_column = "翌日PM duty"
    for old_column in ("原則、宿直を外す曜日", "入れない曜日(半角カンマ区切り)", "入れない曜日"):
        if old_column not in df.columns:
            continue
        if weekday_column not in df.columns:
            df = df.rename(columns={old_column: weekday_column})
        else:
            # 両方の列がある場合は新名称の値を優先し、空欄だけ旧列で補う。
            blank = df[weekday_column].fillna("").astype(str).str.strip().eq("")
            df.loc[blank, weekday_column] = df.loc[blank, old_column]
            df = df.drop(columns=[old_column])
    return df

@st.cache_resource
def horizontal_ng_component(html_source):
    import tempfile
    from pathlib import Path
    import streamlit.components.v1 as components
    directory = Path(tempfile.mkdtemp(prefix="shift_ng_calendar_"))
    (directory / "index.html").write_text(html_source, encoding="utf-8")
    import hashlib
    asset_id = hashlib.sha256(html_source.encode("utf-8")).hexdigest()[:16]
    return components.declare_component(f"shift_ng_{asset_id}", path=str(directory))

HORIZONTAL_NG_HTML = '<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>\n*{box-sizing:border-box}body{margin:0;font-family:system-ui,sans-serif;color:#243247;background:white;font-size:14px}.strip{display:flex;gap:8px;overflow-x:auto;width:100%;padding:6px 2px 16px;align-items:stretch;scrollbar-width:auto}.cell{flex:0 0 112px;width:112px;min-width:112px;border:2px solid #dfe3ea;border-radius:9px;padding:6px;background:#f8fafc}.head{height:78px;display:flex;flex-direction:column;justify-content:center;align-items:center;border-radius:5px;gap:5px;font-weight:750;white-space:nowrap}.day{font-size:16px}.state{font-size:14px}.day.holiday{color:#c92336}.day.saturday{color:#1670c5}select{width:100%;height:36px;margin-top:6px;font-size:14px;font-weight:650;border:1px solid #8b95a5;border-radius:5px;background:white;color:#243247;padding:2px}button{background:#ff4b4b;color:white;border:0;border-radius:7px;padding:12px 18px;font:600 14px system-ui;cursor:pointer}button:focus-visible,select:focus-visible{outline:3px solid #4789ff;outline-offset:2px}.note{margin:8px 0;font-size:13px;color:#566174;min-height:20px}\n\n.strip.month{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:6px;overflow:visible;padding-bottom:8px}\n.month .cell{width:auto;min-width:0;padding:5px;flex:none}\n.month .head{height:72px}.weekday{text-align:center;font-weight:700;padding:4px}.blank{min-height:126px;background:#f5f6f8;border-radius:9px}\n@media(max-width:600px){.strip.month{gap:3px}.month .cell{padding:2px;border-width:1px}.month .day{font-size:12px}.month .state{font-size:11px}.month select{font-size:11px;padding:0;height:30px}.month .head{height:66px}.month .blank{min-height:108px}.weekday{font-size:12px}}\n\n/* 上段が日直、下段が宿直。不可の勤務帯だけ塗る。 */\n.cell,.month .cell{background:#fff;border-color:#cbd2dc}\n.head,.month .head{height:124px;gap:4px;justify-content:flex-start;padding-top:2px;color:#243247;background:transparent}\n.state{width:100%;display:grid;grid-template-rows:repeat(2,29px);gap:0;border:1px solid #d6dce5;border-radius:5px;overflow:hidden;order:3}\n.band{display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:750;background:#fff;color:#425268;white-space:nowrap}\n.band + .band{border-top:1px solid #d6dce5}.band.off{background:#fcfcfd;color:#d8dde5;font-weight:400}\n.cell[data-state="全NG"] .band{background:#b42332;color:#fff}\n.cell[data-state="日NG"] .day-band{background:#9a4700;color:#fff}\n.cell[data-state="宿NG"] .night-band{background:#1856a4;color:#fff}\n.warning-slot{height:22px;min-height:22px;display:flex;align-items:center;justify-content:center}\n.weekday-warning{color:#bf5700;background:#fff0c2;border:1px solid #ef9b20;border-radius:4px;padding:0 4px;font-size:14px;font-weight:900;line-height:20px}\n.blank{min-height:176px}\n@media(max-width:600px){.month .head{height:120px}.month .band{font-size:10px}.month .weekday-warning{font-size:15px;padding:0 3px}.month .blank{min-height:160px}}\n\n.weekday-warning{display:inline-flex;align-items:center;justify-content:center;gap:3px;max-width:100%}\n.duty-label{font-size:9px;font-weight:650;line-height:1.15;white-space:nowrap}\n@media(max-width:600px){.month .weekday-warning{gap:1px;padding:0 1px;font-size:12px}.month .duty-label{font-size:8px;white-space:normal;max-width:30px;overflow-wrap:anywhere}}\n\n/* 日付の文字・休日色・警告の有無によらず各段の位置を固定する。 */\n.head,.month .head{\n display:grid;\n grid-template-columns:minmax(0,1fr);\n grid-template-rows:26px 30px 60px;\n justify-content:stretch;\n width:100%;\n min-width:0;\n align-content:end;\n align-items:center;\n justify-items:center;\n gap:4px;\n padding-top:0;\n padding-bottom:0;\n}\n.head > .day{line-height:24px;margin:0;align-self:center}\n.head > .warning-slot{height:30px;min-height:30px;width:100%;margin:0}\n.head > .state{height:60px;min-height:60px;margin:0;align-self:end}\n@media(max-width:600px){\n .month .head{grid-template-rows:22px 30px 60px}\n}\n</style><body><div id="strip" class="strip" aria-label="NG日カレンダー"></div><div id="note" class="note">左右へスクロールして選択できます。</div><button id="apply" type="button">NG日を保存する</button><script>\nlet version=null,days=[],draft=[],seen=null;let mode=\'row\';let frameHeight=0;function resize(){let h=document.body.scrollHeight+10;if(h!==frameHeight){frameHeight=h;send(\'streamlit:setFrameHeight\',{height:h})}}const labels={OK:\'OK\',\'全NG\':\'✕ 全NG\',\'日NG\':\'☀ 日NG\',\'宿NG\':\'☾ 宿NG\'};\nfunction send(type,data={}){window.parent.postMessage({isStreamlitMessage:true,type,...data},\'*\')}\nfunction paint(cell,value){cell.dataset.state=value;let holiday=cell.dataset.holiday===\'true\';cell.querySelector(\'.day-band\').textContent=holiday?(value===\'全NG\'||value===\'日NG\'?\'日直NG\':\'日直可\'):\'日直なし\';cell.querySelector(\'.night-band\').textContent=value===\'全NG\'||value===\'宿NG\'?\'宿直NG\':\'宿直可\';}\nwindow.addEventListener(\'message\',(event)=>{if(event.data.type!==\'streamlit:render\')return;let a=event.data.args;document.getElementById(\'apply\').textContent=a.doctor+\'先生のNG日を保存する\';if(a.version!==version){version=a.version;mode=a.mode||\'row\';days=a.days;draft=days.map(d=>d.value);let strip=document.getElementById(\'strip\');strip.replaceChildren();strip.className=\'strip \'+(mode===\'month\'?\'month\':\'\');if(mode===\'month\'){[\'月\',\'火\',\'水\',\'木\',\'金\',\'土\',\'日\'].forEach((w,i)=>{let el=document.createElement(\'div\');el.className=\'weekday\';el.textContent=w;el.style.color=i===6?\'#c92336\':i===5?\'#1670c5\':\'#243247\';strip.append(el)});for(let i=0;i<a.offset;i++){let el=document.createElement(\'div\');el.className=\'blank\';strip.append(el)}}days.forEach((d,i)=>{let cell=document.createElement(\'div\');cell.className=\'cell\';cell.dataset.holiday=String(d.options.includes(\'日NG\'));let head=document.createElement(\'div\');head.className=\'head\';let day=document.createElement(\'div\');day.className=\'day \'+d.kind;day.textContent=mode===\'month\'?d.day+\'日\':d.day+\'日（\'+d.weekday+\'）\';let state=document.createElement(\'div\');state.className=\'state\';let dayBand=document.createElement(\'div\');dayBand.className=\'band day-band\'+(d.options.includes(\'日NG\')?\'\':\' off\');let nightBand=document.createElement(\'div\');nightBand.className=\'band night-band\';state.append(dayBand,nightBand);let warningSlot=document.createElement(\'div\');warningSlot.className=\'warning-slot\';if(d.warning){let warning=document.createElement(\'span\');warning.className=\'weekday-warning\';warning.textContent=\'⚠︎\';let duty=document.createElement(\'small\');duty.className=\'duty-label\';duty.textContent=\'翌日PM duty\';warning.append(duty);warning.title=\'翌日PM duty（翌日が休日なら例外あり）\';warning.setAttribute(\'aria-label\',warning.title);warningSlot.append(warning)}head.append(day,warningSlot,state);let sel=document.createElement(\'select\');sel.setAttribute(\'aria-label\',d.day+\'日のNG設定\');d.options.forEach(v=>{let o=document.createElement(\'option\');o.value=v;o.textContent=labels[v];sel.append(o)});sel.value=d.value;sel.onchange=()=>{draft[i]=sel.value;paint(cell,sel.value);document.getElementById(\'note\').textContent=\'未保存の変更があります。選び終わったら下のボタンを押してください。\'};cell.append(head,sel);paint(cell,d.value);strip.append(cell)});if(mode===\'month\'){let blanks=(7-(a.offset+days.length)%7)%7;for(let i=0;i<blanks;i++){let el=document.createElement(\'div\');el.className=\'blank\';strip.append(el)}}document.getElementById(\'note\').textContent=\'NGを選ぶと色が変わります。選び終わったら保存してください。\';}resize()});\ndocument.getElementById(\'apply\').onclick=()=>{send(\'streamlit:setComponentValue\',{value:{version,values:draft,token:Date.now().toString()+\'-\'+Math.random()},dataType:\'json\'});document.getElementById(\'note\').textContent=\'保存しています…\';};new ResizeObserver(resize).observe(document.body);send(\'streamlit:componentReady\',{apiVersion:1});resize();\n</script></body></html>'