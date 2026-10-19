export const pct=(v)=>`${Math.round((v||0)*100)}%`;
export const dateTime=(s)=>new Date(s).toLocaleString('vi-VN',{dateStyle:'short',timeStyle:'short'});
export function Status({abnormal}){return <span className={`pill ${abnormal?'pill-bad':'pill-ok'}`}>{abnormal?'● Bất thường':'● Bình thường'}</span>}
export function Empty({children}){return <div className="text-center py-12 text-slate-400 text-sm">{children}</div>}
