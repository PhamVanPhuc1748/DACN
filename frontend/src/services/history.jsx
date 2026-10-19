import {createContext,useContext,useState} from 'react';import {seedHistory} from '../data/mock';
const C=createContext(null);
// Chỉ lưu metadata; file ảnh không lưu vào localStorage để tránh vượt dung lượng.
function initial(){try{const x=JSON.parse(localStorage.getItem('pigskin-history-v1')||'null');return Array.isArray(x)?x:seedHistory;}catch{return seedHistory;}}
export function HistoryProvider({children}){const [history,setHistory]=useState(initial);function save(next){setHistory(next);try{localStorage.setItem('pigskin-history-v1',JSON.stringify(next));}catch{}}return <C.Provider value={{history,add:(r)=>save([r,...history]),clear:()=>save([])}}>{children}</C.Provider>}
export function useHistory(){return useContext(C)}
