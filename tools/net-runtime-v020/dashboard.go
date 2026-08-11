package main

import (
	"io"
	"net"
	"os"
	"strings"
	"time"
)

const page = `<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SR1010 WireGuard</title><style>body{margin:0;background:#0b1220;color:#dbeafe;font:15px system-ui}main{max-width:850px;margin:auto;padding:24px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}.card{background:#152238;border:1px solid #263b5b;border-radius:14px;padding:17px}.v{font-size:25px;font-weight:700;color:#67e8f9}.ok{color:#4ade80}.bad{color:#fb7185}small{color:#94a3b8}pre{white-space:pre-wrap}</style><main><h1>SR1010 WireGuard</h1><p><small>只读状态面板，仅通过 WireGuard 隧道提供。</small></p><div class="grid"><div class="card">运行状态<div class="v" id="state">读取中</div></div><div class="card">监听端口<div class="v" id="port">—</div></div><div class="card">Peer 数量<div class="v" id="peers">—</div></div><div class="card">最近握手<div class="v" id="handshake">—</div></div></div><h2>流量</h2><div class="card"><pre id="traffic">读取中…</pre></div></main><script>function size(n){for(const u of ['B','KiB','MiB','GiB']){if(n<1024)return n.toFixed(n<10?1:0)+' '+u;n/=1024}return n.toFixed(1)+' TiB'}function ago(t){if(!t)return'尚未握手';let s=Math.max(0,Math.floor(Date.now()/1000-t));if(s<60)return s+' 秒前';if(s<3600)return Math.floor(s/60)+' 分钟前';return Math.floor(s/3600)+' 小时前'}async function load(){try{let x=await fetch('/status.json?'+Date.now()).then(r=>r.json());state.textContent=x.running?'运行中':'异常';state.className='v '+(x.running?'ok':'bad');port.textContent=x.listen_port;peers.textContent=x.peer_count;handshake.textContent=ago(x.latest_handshake);traffic.textContent='接收：'+size(x.rx_bytes)+'\n发送：'+size(x.tx_bytes)+'\n接口：'+x.interface}catch(e){state.textContent='读取失败';state.className='v bad'}}load();setInterval(load,5000)</script></html>`

func respond(c net.Conn, code, typ string, body []byte) {
	h := "HTTP/1.1 " + code + "\r\nContent-Type: " + typ + "\r\nCache-Control: no-store\r\nContent-Length: " + itoa(len(body)) + "\r\nConnection: close\r\n\r\n"
	io.WriteString(c, h); c.Write(body)
}
func itoa(n int) string { if n==0{return "0"}; b:=make([]byte,0,12);for n>0{b=append(b,byte('0'+n%10));n/=10};for i,j:=0,len(b)-1;i<j;i,j=i+1,j-1{b[i],b[j]=b[j],b[i]};return string(b) }
func handle(c net.Conn) {
	defer c.Close(); c.SetDeadline(time.Now().Add(4*time.Second)); buf:=make([]byte,1024);n,_:=c.Read(buf);line:=strings.SplitN(string(buf[:n]),"\r\n",2)[0]
	if strings.HasPrefix(line,"GET /status.json") { b,e:=os.ReadFile("/opt/sr1010-net-runtime/state/dashboard.json");if e!=nil{respond(c,"503 Service Unavailable","application/json",[]byte(`{"running":false}`));return};respond(c,"200 OK","application/json",b);return }
	if strings.HasPrefix(line,"GET / ") { respond(c,"200 OK","text/html; charset=utf-8",[]byte(page));return }
	respond(c,"404 Not Found","text/plain",[]byte("not found\n"))
}
func main(){addr:=os.Getenv("DASHBOARD_LISTEN");if addr==""{addr="10.77.0.1:51889"};l,e:=net.Listen("tcp",addr);if e!=nil{panic(e)};for{c,e:=l.Accept();if e==nil{go handle(c)}}}
