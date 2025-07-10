module.exports = async function bot_SII_rol(page, predio, manzana, variables) {

    // presionar "aceptar" en aviso
    await page.waitForSelector('//*[@id="ng-app"]/body/div[6]/div/div/div[3]/div/button');
    await page.click('//*[@id="ng-app"]/body/div[6]/div/div/div[3]/div/button');

    //*[@id="titulo"]/div[8]/i "buscar Rol"
    await page.waitForSelector('//*[@id="titulo"]/div[8]/i');
    await page.click('//*[@id="titulo"]/div[8]/i');
    await page.waitForTimeout(1000); // Esperar un segundo para que se cierre el modal
    

    // llenar campo //*[@id="rolsearch"]/div[2]/div[1]/input con variables predefinidas
    await page.click('//*[@id="rolsearch"]/div[2]/div[1]/input');
    await page.fill('//*[@id="rolsearch"]/div[2]/div[1]/input', '');
    await page.type('//*[@id="rolsearch"]/div[2]/div[1]/input', variables.comuna, { delay: 100 });

    await page.waitForFunction(() => {
        const items = document.querySelectorAll('ul[role="listbox"] li');
        return items.length > 0;
    }, { timeout: 7000 });

    const seleccionoComuna = await page.evaluate((comunaObjetivo) => {
        const normalizar = str => str.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase();
        const opciones = document.querySelectorAll('ul[role="listbox"] li');
        const objetivo = normalizar(comunaObjetivo);

        for (const opcion of opciones) {
            const texto = normalizar(opcion.innerText);
            if (texto.includes(objetivo)) {
                opcion.click();
                return true;
            }
        }
        return false;
    }, variables.comuna);

    await page.fill('//*[@id="rolsearch"]/div[2]/div[2]/input', manzana, { delay: 500 });
    await page.fill('//*[@id="rolsearch"]/div[2]/div[3]/input', predio, { delay: 500 });

    await page.waitForTimeout(1000); 

    // seleccionar el boton buscar
    await page.waitForFunction(() => {
    const boton = document.querySelector('#rolsearch div:nth-child(2) div:nth-child(4) div button');
        return boton && !boton.disabled;
    }, { timeout: 15000 });
    await page.click('//*[@id="rolsearch"]/div[2]/div[4]/div/button[1]');



    await page.waitForTimeout(2000); 

    // Extraer los textos
    const direccion = await page.locator('xpath=//*[@id="preview"]/div[1]/div[5]').textContent();
    const avaluoTotal_c = await page.locator('xpath=//*[@id="preview"]/div[2]/div[2]/span').textContent();


    // Mostrar los valores
    console.log('Avaluo Total:', avaluoTotal_c);


    return {
        avaluoTotal: avaluoTotal_c,
        direccion: direccion.trim(),
    };
}
