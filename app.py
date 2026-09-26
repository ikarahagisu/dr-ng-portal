import calendar, datetime, hashlib, json
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
import jpholiday
from calendar_ui import parse_staff_csv, horizontal_ng_component, HORIZONTAL_NG_HTML
from merge_requests import merge_requests

st.set_page_config(page_title="当直NG入力", layout="wide")
st.title("当直NG入力")
page=st.sidebar.radio("画面", ["Dr入力", "CSVをまとめる（管理者）"])
today=datetime.datetime.now(ZoneInfo("Asia/Tokyo")).date()
next_month=(today.replace(day=28)+datetime.timedelta(days=4)).replace(day=1)
a,b=st.columns(2)
year=int(a.number_input("年",2000,2100,next_month.year))
month=int(b.number_input("月",1,12,next_month.month))
key=f"{year:04d}-{month:02d}"
ndays=calendar.monthrange(year,month)[1]
holidays=st.multiselect("特別休日（管理者から指定された平日）",list(range(1,ndays+1)),key=f"holidays_{key}")
weekdays=["月","火","水","木","金","土","日"]
def holiday(d):
    dt=datetime.date(year,month,d)
    return dt.weekday()>=5 or jpholiday.is_holiday(dt) or d in holidays
def ng_string(values):
    return ",".join(str(i) if v=="全NG" else f"{i}:{v}" for i,v in enumerate(values,1) if v!="OK")
def parse_ng(value):
    result={}
    for item in str(value or "").replace("：",":").replace("，",",").split(","):
        try:
            pair=item.strip().split(":")
            d=int(pair[0]);v=pair[1] if len(pair)>1 else "全NG"
            if 1<=d<=ndays and v in ("OK","全NG","日NG","宿NG"):result[d]=v
        except (ValueError,IndexError):pass
    return result
def local_time(value):
    return datetime.datetime.fromisoformat(value).astimezone(ZoneInfo("Asia/Tokyo")).strftime("%Y/%m/%d %H:%M:%S")

if page=="CSVをまとめる（管理者）":
    st.subheader("提出CSVを医師条件へ取り込む")
    st.write("元の医師条件CSVと、各Drから受け取った提出CSVを選択してください。回数上限などは元の医師条件を保持します。")
    base=st.file_uploader("元の医師条件CSV",type="csv")
    files=st.file_uploader("各Drの提出CSV（複数選択可）",type="csv",accept_multiple_files=True)
    if base and files:
        try:
            original=parse_staff_csv(base.getvalue()).fillna("")
            submissions=[pd.read_csv(f,encoding="utf-8-sig",keep_default_na=False) for f in files]
            merged,names=merge_requests(original,submissions,year,month,holidays)
            st.success(f"{len(names)}名分を取り込みました。未提出の医師は元の条件を保持しています。")
            st.dataframe(pd.DataFrame({"取り込んだ医師":names}),hide_index=True)
            st.download_button("シフト作成用の医師条件CSVをダウンロード",merged.to_csv(index=False).encode("utf-8-sig"),f"staff_{key}.csv","text/csv")
        except Exception as e:st.error(str(e))
else:
    st.caption("入力内容はサーバーに保管しません。最後に提出用CSVをダウンロードして管理者へ送ってください。")
    doctor=st.text_input("医師名（管理者の名簿と同じ表記）",key=f"doctor_{key}").strip()
    if not doctor:
        st.info("医師名を入力してください。")
        st.stop()
    row={}
    saved=st.session_state.get(f"saved_{key}_{doctor}")
    initial=parse_ng(row.get("NG日(半角カンマ区切り)",""))
    values=saved["values"] if saved else [initial.get(d,"OK") for d in range(1,ndays+1)]
    initial_duty=saved["duty"] if saved else [w for w in weekdays if w in str(row.get("翌日PM duty",""))]
    duty=st.multiselect("翌日PM duty",weekdays,default=initial_duty,key=f"duty_{key}_{doctor}",
        help="木曜PMにdutyがある場合は「水」を選びます。日直は対象外です。")
    mode=st.radio("NGカレンダーの表示",["月間カレンダー","1日〜月末を横一列"],horizontal=True,key=f"mode_{key}_{doctor}")
    st.info("当直NGを選択してください。最後に「NG日を保存する」を押してください。")
    st.caption("医師・月・表示・曜日設定を切り替える前に、NG日を保存してください。")
    if saved:st.success("保存済み："+local_time(saved["updated"])+"　／　NG日："+(ng_string(values) or "なし"))
    else:st.caption("まだ保存されていません。NG日を入力してください。")
    st.markdown("<div style='color:#bf5700;background:#fff0c2;border:1px solid #ef9b20;border-radius:6px;padding:8px 10px;font-weight:600'>⚠は、翌日PMにdutyがあるため、原則としてその日の宿直を外すことを示します。ただし、翌日が休日の場合は宿直に入ることがあります。</div>",unsafe_allow_html=True)
    days=[]
    for d in range(1,ndays+1):
        dt=datetime.date(year,month,d);hol=holiday(d)
        opts=["OK","全NG","日NG","宿NG"] if hol else ["OK","宿NG"]
        val=values[d-1]
        if val not in opts:val="宿NG" if val=="全NG" else "OK"
        days.append(dict(day=d,weekday=weekdays[dt.weekday()],options=opts,value=val,warning=weekdays[dt.weekday()] in duty,
            kind="holiday" if hol and (dt.weekday()!=5 or jpholiday.is_holiday(dt) or d in holidays) else ("saturday" if dt.weekday()==5 else "weekday")))
    rev=hashlib.sha256(json.dumps([key,doctor,mode,days,saved],ensure_ascii=False).encode()).hexdigest()
    ck=f"calendar_{key}_{doctor}_{mode}"
    response=horizontal_ng_component(HORIZONTAL_NG_HTML)(days=days,mode="month" if mode=="月間カレンダー" else "row",
        offset=datetime.date(year,month,1).weekday(),doctor=doctor,version=rev,key=ck,default=None)
    if isinstance(response,dict) and response.get("token")!=st.session_state.get(ck+"_seen"):
        st.session_state[ck+"_seen"]=response.get("token")
        vals=response.get("values")
        if response.get("version")==rev and isinstance(vals,list) and len(vals)==ndays and all(v in d["options"] for v,d in zip(vals,days)):
            st.session_state[f"saved_{key}_{doctor}"]=dict(values=vals,duty=duty,holidays=list(holidays),updated=datetime.datetime.now(datetime.timezone.utc).isoformat())
            st.rerun()

    if saved:
        submission=pd.DataFrame([{"対象年":year,"対象月":month,"先生の名前":doctor,
            "NG日(半角カンマ区切り)":ng_string(saved["values"]),
            "翌日PM duty":",".join(saved["duty"]),"特別休日":",".join(map(str,sorted(saved["holidays"])))}])
        st.download_button("提出用CSVをダウンロード",submission.to_csv(index=False).encode("utf-8-sig"),f"ng_{key}_{doctor}.csv","text/csv")
        st.caption("変更した場合は「NG日を保存する」を押してから、もう一度ダウンロードしてください。CSVはメールなどで管理者へ提出してください。")
