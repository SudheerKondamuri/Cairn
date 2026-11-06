import { spawn,execFileSync } from "node:child_process";
import {existsSync} from "node:fs";
import {resolve} from "node:path";
const name=`cairn-browser-${process.pid}`;
execFileSync("docker",["run","--rm","-d","--name",name,"-e","POSTGRES_HOST_AUTH_METHOD=trust","-p","127.0.0.1::5432","postgres:16-alpine"],{stdio:"pipe"});
for(let i=0;i<60;i++){
 try{execFileSync("docker",["exec",name,"pg_isready","-U","postgres"],{stdio:"pipe"});break;}catch{await new Promise(r=>setTimeout(r,500));}
}
await new Promise(r=>setTimeout(r,1500));
const port=execFileSync("docker",["port",name,"5432"],{encoding:"utf8"}).trim().split(":").pop();
const python=existsSync("../.venv/bin/python")?resolve("../.venv/bin/python"):"python3";
const api=spawn(python,["tests/support/api_fixture.py"],{stdio:"inherit",env:{...process.env,DATABASE_URL:`postgresql://postgres@127.0.0.1:${port}/postgres`}});
const web=spawn(process.execPath,[".next/standalone/server.js"],{stdio:"inherit",env:{...process.env,HOSTNAME:"127.0.0.1",PORT:"3100"}});
let stopped=false;
function stop(){if(stopped)return;stopped=true;api.kill();web.kill();try{execFileSync("docker",["stop",name],{stdio:"pipe"});}catch{}}
process.on("SIGTERM",stop);process.on("SIGINT",stop);process.on("exit",stop);
for(const child of [api,web])child.on("exit",()=>{stop();process.exit();});
