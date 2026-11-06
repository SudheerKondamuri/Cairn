import {test,expect} from "@playwright/test";
import {mkdir} from "node:fs/promises";
import {login} from "./support/login";
test("new account screens render at desktop and phone sizes",async({page},info)=>{
 test.skip(info.project.name!=="desktop");
 await mkdir("../.impeccable/review/accounts",{recursive:true});
 for(const width of [1440,390]){
  await page.context().clearCookies();await page.setViewportSize({width,height:1000});
  await page.goto("/operator/sign-in");await page.evaluate(()=>document.fonts.ready);
  await page.screenshot({path:`../.impeccable/review/accounts/signin-${width}.png`,fullPage:true});
  await login(page,"browser-admin");
  for(const [name,path] of [["workspace","/operator"],["source","/operator/investigations/new"],["admin","/operator/admin"]]){
   await page.goto(path);await expect(page.locator(".allowance-strip strong")).toContainText("investigations available");
   await page.evaluate(()=>document.fonts.ready);
   if(name==="source")await page.getByLabel("Source location").selectOption("github");
   await page.screenshot({path:`../.impeccable/review/accounts/${name}-${width}.png`,fullPage:true});
   expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  }
 }
});
