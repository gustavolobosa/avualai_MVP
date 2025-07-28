import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const browser = await chromium.launch({ headless: false });
const page = await browser.newPage();
await page.goto('https://www.sii.cl/destacados/reavaluo/2022/4324-4330.html');

await page.waitForSelector('xpath=//*[@id="my-wrapper"]/div[2]/div/div/div[2]/div[1]/div/div[1]/div/div/button/span[1]');
await page.click('xpath=//*[@id="my-wrapper"]/div[2]/div/div/div[2]/div[1]/div/div[1]/div/div/button/span[1]');

// 3. Esperar los <li> de la lista desplegada
await page.waitForSelector('ul.dropdown-menu.inner li');

// 4. Obtener todas las opciones de la lista
const regiones = await page.$$('ul.dropdown-menu.inner li');

console.log(`🔁 Total de regiones encontradas: ${regiones.length}`);

await page.waitForSelector('xpath=//*[@id="my-wrapper"]/div[2]/div/div/div[2]/div[1]/div/div[1]/div/div/button/span[1]');
await page.click('xpath=//*[@id="my-wrapper"]/div[2]/div/div/div[2]/div[1]/div/div[1]/div/div/button/span[1]');

for (let i = 1; i < regiones.length; i++) {
    // Reabrir el dropdown antes de cada clic si se colapsa
    await page.click('xpath=//*[@id="my-wrapper"]/div[2]/div/div/div[2]/div[1]/div/div[1]/div/div/button/span[1]');
    
    await page.waitForSelector('ul.dropdown-menu.inner li');

    const opciones = await page.$$('ul.dropdown-menu.inner li');
    const region = opciones[i];

    const texto_region = await region.innerText();
    console.log(`🖱️ Clic en: ${texto_region}`);
    await region.click();
    await page.waitForTimeout(1000); // Espera opcional para ver qué pasa luego

    await page.click('xpath=//*[@id="my-wrapper"]/div[2]/div/div/div[2]/div[1]/div/div[2]/div/div/button/span[1]');

    const comunas = await page.$$('ul.dropdown-menu.inner li');
    console.log(`🔁 Total de comunas encontradas: ${comunas.length}`);

    await page.click('xpath=//*[@id="my-wrapper"]/div[2]/div/div/div[2]/div[1]/div/div[2]/div/div/button/span[1]');

    for (let c = comunas.length - 1; c >= (regiones.length); c--) { 
        await page.click('xpath=//*[@id="my-wrapper"]/div[2]/div/div/div[2]/div[1]/div/div[2]/div/div/button/span[1]');

        const opciones_comunas = await page.$$('ul.dropdown-menu.inner li');
        const comuna = opciones_comunas[c];

        const texto_comuna = await comuna.innerText();
        console.log(`🏙️ Seleccionando comuna: ${texto_comuna}`);

        await comuna.click();
        await page.waitForTimeout(2000); // Esperar para ver resultados si los hay

        // Buscar el <a> que contiene el <i class="fa fa-file-pdf-o fa-rojo">
        const enlacePDF = await page.$('a:has(i.fa-file-pdf-o.fa-rojo)');

        if (enlacePDF) {
            const url = await enlacePDF.getAttribute('href');

            const descargaDir = path.resolve('descargas/reavaluos');
            const fileName = `REAVALUO_${texto_region}_${texto_comuna}.pdf`;
            const filePath = path.join(descargaDir, fileName);

            if (!fs.existsSync(descargaDir)) {
                fs.mkdirSync(descargaDir, { recursive: true });
            }

            const fullUrl = new URL(url, page.url()).href;
            const response = await fetch(fullUrl);
            const buffer = await response.arrayBuffer();

            fs.writeFileSync(filePath, Buffer.from(buffer));
            console.log(`📥 Descargado: ${fileName}`);
        } else {
            console.log('❌ No se encontró el enlace con el ícono PDF para esta comuna');
        }

    }

    
  
}
