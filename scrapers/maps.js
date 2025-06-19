module.exports = async function bot_SII_maps(page, variables) {

    // presionar un boton con xpath
    await page.waitForSelector('//*[@id="ng-app"]/body/div[5]/div/div/div[3]/div/button');
    await page.click('//*[@id="ng-app"]/body/div[5]/div/div/div[3]/div/button');

    await page.waitForTimeout(500); 

    //*[@id="titulo"]/div[7]/i
    await page.waitForSelector('//*[@id="titulo"]/div[7]/i');
    await page.click('//*[@id="titulo"]/div[7]/i');

    await page.waitForTimeout(500); 

    // presionar buscar comunas
    await page.waitForSelector('//*[@id="titulo"]/div[5]/i');
    await page.click('//*[@id="titulo"]/div[5]/i');

    await page.waitForTimeout(500); 

    // 👉 Función para normalizar texto (quitar tildes y poner mayúsculas)
    const normalizar = str =>
        str.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase();

    // ✅ Seleccionar región
    const regionNormalizada = normalizar(variables.region);

    // Esperar a que se cargue la lista de regiones
    await page.waitForFunction(() => {
        const select = document.querySelector('#regionSeleccionada');
        return select && select.options.length > 1;
    }, { timeout: 10000 });

    const regiones = await page.$$eval('#regionSeleccionada option', opts =>
        opts.map(o => ({ value: o.value, label: o.label }))
    );

    const opcionRegion = regiones.find(o =>
        normalizar(o.label).includes(regionNormalizada)
    );

    if (opcionRegion) {
        await page.selectOption('#regionSeleccionada', opcionRegion.value);
        console.log(`Región seleccionada: ${opcionRegion.label}`);
    } else {
        console.log(`Región "${variables.region}" no encontrada.`);
        return;
    }

    // 🕒 Esperar a que se cargue la lista de comunas (depende del sistema, puede necesitar más tiempo)
    await page.waitForTimeout(2000);
    await page.waitForSelector('#comunaSeleccionada');

    // Seleccionar comuna
    const comunaNormalizada = normalizar(variables.comuna);

    const comunas = await page.$$eval('#comunaSeleccionada option', opts =>
        opts.map(o => ({ value: o.value, label: o.label }))
    );

    const opcionComuna = comunas.find(o =>
        normalizar(o.label).includes(comunaNormalizada)
    );

    if (opcionComuna) {
        await page.selectOption('#comunaSeleccionada', opcionComuna.value);
        console.log(`Comuna seleccionada: ${opcionComuna.label}`);
    } else {
        console.log(`Comuna "${variables.comuna}" no encontrada.`);
        await browser.close();
        return;
    }

    // presionar el boton buscar //*[@id="layersearch"]/div[2]/div[2]/div/button[1]
    await page.waitForTimeout(1000); 
    await page.waitForSelector('//*[@id="layersearch"]/div[2]/div[2]/div/button[1]');
    await page.click('//*[@id="layersearch"]/div[2]/div[2]/div/button[1]');

    // presionar boton obserbatorio de mercado de suelo //*[@id="layersearch"]/div[2]/div[3]/table/tbody/tr[16]/td[2]/button
    await page.waitForSelector('//*[@id="layersearch"]/div[2]/div[3]/table/tbody/tr[16]/td[2]/button');
    await page.click('//*[@id="layersearch"]/div[2]/div[3]/table/tbody/tr[16]/td[2]/button');

    //clikear el centro del mapa
    await page.waitForSelector('#mapaid', {state: 'visible', timeout: 10000 });

    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(1000); 

    const mapElement = await page.$('#mapaid');

    const boundingBox = await mapElement.boundingBox();

    const centerX = boundingBox.x + boundingBox.width / 2;
    const centerY = boundingBox.y + boundingBox.height / 2;

    console.log(`Centro del mapa: (${centerX}, ${centerY})`);

    await page.mouse.click(centerX, centerY);

    await page.waitForTimeout(2000); 
}
