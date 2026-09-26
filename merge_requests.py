import calendar
import pandas as pd

def merge_requests(base, submissions, year, month, holidays):
    if "先生の名前" not in base:raise ValueError("元のCSVに「先生の名前」列が必要です。")
    out=base.copy()
    out["先生の名前"]=out["先生の名前"].astype(str).str.strip()
    if out["先生の名前"].duplicated().any():raise ValueError("元の名簿に同名の医師がいます。区別できる名前にしてください。")
    names=[]
    for df in submissions:
        required={"対象年","対象月","先生の名前","NG日(半角カンマ区切り)","翌日PM duty","特別休日"}
        if not required.issubset(df.columns) or len(df)!=1:raise ValueError("提出用CSVではないファイルが含まれています。")
        row=df.iloc[0];name=str(row["先生の名前"]).strip()
        if int(row["対象年"])!=year or int(row["対象月"])!=month:raise ValueError(f"{name}：対象年月が違います。")
        if name in names:raise ValueError(f"{name}：提出CSVが重複しています。最新版だけ選択してください。")
        if name not in out["先生の名前"].values:raise ValueError(f"{name}：名簿にありません。氏名の表記を確認してください。")
        hs={int(x) for x in str(row["特別休日"]).split(",") if x.strip()}
        if hs!=set(holidays):raise ValueError(f"{name}：特別休日の設定が一致しません。")
        for item in str(row["NG日(半角カンマ区切り)"]).split(","):
            if not item:continue
            pair=item.split(":")
            if len(pair)>2 or not 1<=int(pair[0])<=calendar.monthrange(year,month)[1] or (len(pair)==2 and pair[1] not in ("全NG","日NG","宿NG")):
                raise ValueError(f"{name}：NG日が不正です。")
        if any(w not in "月火水木金土日" or len(w)!=1 for w in str(row["翌日PM duty"]).split(",") if w):
            raise ValueError(f"{name}：翌日PM dutyの曜日が不正です。")
        for col in ("NG日(半角カンマ区切り)","翌日PM duty"):
            out.loc[out["先生の名前"]==name,col]=str(row[col])
        names.append(name)
    return out,names
