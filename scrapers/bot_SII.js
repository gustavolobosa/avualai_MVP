module.exports = async function bot_SII_rol(page, variables) {

    //*[@id="titulo"]/div[7]/i
    await page.waitForSelector('//*[@id="titulo"]/div[7]/i');
    await page.click('//*[@id="titulo"]/div[7]/i');
    await page.waitForTimeout(1000); // Esperar un segundo para que se cierre el modal
    

    // llenar campo //*[@id="addresssearch"]/div[2]/div[1]/input con variables predefinidas
    await page.click('xpath=//*[@id="addresssearch"]/div[2]/div[1]/input');
    await page.fill('xpath=//*[@id="addresssearch"]/div[2]/div[1]/input', '');
    await page.type('xpath=//*[@id="addresssearch"]/div[2]/div[1]/input', variables.comuna, { delay: 100 });

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

    await page.fill('//*[@id="addresssearch"]/div[2]/div[2]/input', variables.direccion, { delay: 500 });
    await page.fill('//*[@id="addresssearch"]/div[2]/div[3]/input', variables.numero, { delay: 500 });

    await page.waitForTimeout(1000); 

    // seleccionar el boton buscar
    await page.waitForFunction(() => {
    const boton = document.querySelector('#addresssearch div:nth-child(2) div:nth-child(9) div button');
        return boton && !boton.disabled;
    }, { timeout: 15000 });
    await page.click('//*[@id="addresssearch"]/div[2]/div[9]/div/button[1]');


    // esperar a que aparezca el boton de ver detalles
    await page.waitForSelector('//*[@id="ng-app"]/body/div[6]/div/div/div/div[2]/table/tbody/tr/td[4]/button', { timeout: 10000 });
    await page.click('//*[@id="ng-app"]/body/div[6]/div/div/div/div[2]/table/tbody/tr/td[4]/button');
                      //*[@id="ng-app"]/body/div[6]/div/div/div/div[2]/table/tbody/tr/td[4]/button

    await page.waitForTimeout(3000); 

    // Extraer los textos
    const rol = await page.locator('//*[@id="preview"]/div[1]/div[4]/span').textContent();
    const ubicacion = await page.locator('//*[@id="preview"]/div[1]/div[6]/div[1]').textContent();
    const destino = await page.locator('//*[@id="preview"]/div[1]/div[6]/div[3]').textContent();
    const reavaluo = await page.locator('//*[@id="preview"]/div[1]/div[6]/div[2]/span').textContent();

    // Mostrar los valores
    console.log('------------------------------------------');
    console.log('Rol Predial:', rol);
    console.log('Ubicacion:', ubicacion);
    console.log('Destino:', destino);
    console.log('Reavaluo:', reavaluo);
    console.log('------------------------------------------');

    // la manzana sera la primera parte del rol antes del guion
    const manzana = rol.split('-')[0].trim();
    const predio = rol.split('-')[1].trim();

    // Extraer los textos
    const avaluoTotal = await page.locator('xpath=//*[@id="preview"]/div[2]/div[2]/span').textContent();
    const avaluoAfecto = await page.locator('xpath=//*[@id="preview"]/div[2]/div[3]/span').textContent();
    const avaluoExento = await page.locator('xpath=//*[@id="preview"]/div[2]/div[4]/span').textContent();

    // Mostrar los valores
    console.log('Avaluo Total:', avaluoTotal);
    console.log('Avaluo Afecto:', avaluoAfecto);
    console.log('Avaluo Exento:', avaluoExento);
    console.log('------------------------------------------');


    // Esperar a que aparezca el botón de (+) para ver detalles de áreas homogéneas
    await page.waitForSelector('//*[@id="preview"]/div[4]/div[1]/div[1]/span');
    await page.click('//*[@id="preview"]/div[4]/div[1]/div[1]/span');

    // Extraer los textos
    const codAreaHomo = await page.locator('//*[@id="preview"]/div[4]/div[1]/div[2]/div').textContent();
    const rangoSupPred = await page.locator('//*[@id="preview"]/div[4]/div[1]/div[3]/div').textContent();
    const valM2 = await page.locator('//*[@id="preview"]/div[4]/div[1]/div[4]/div').textContent();

    // Mostrar los valores
    console.log('Código Área Homogénea:', codAreaHomo);
    console.log('Rango Superficie Predial:', rangoSupPred);
    console.log('Valor por Metro Cuadrado:', valM2);
    console.log('------------------------------------------');

    // Presionar el botón de (+) para ver detalles de observatorio mercado de suelo urbano 2022 //*[@id="preview"]/div[4]/div[2]/div[1]/span
    await page.waitForSelector('//*[@id="preview"]/div[4]/div[2]/div[1]/span');
    await page.click('//*[@id="preview"]/div[4]/div[2]/div[1]/span');

    const valComM2 = await page.locator('//*[@id="preview"]/div[4]/div[2]/div[5]/div').textContent();

    //convertir el valor anterior a float y multiplicarlo por 4
    const valComM2Float = parseFloat(valComM2.replace(/\./g, '').replace('$', '').replace(',', '.')) * 39235;
    console.log('Valor Comercial por Metro Cuadrado:', valComM2Float);
    console.log('------------------------------------------');

    // el valM2 es un % del valComM2Float
    const valM2Parsed = valM2.replace(/\./g, '').replace('$', '').replace(',', '.');
    // from 37.67 to $37
    const valComM2FloatParsed = valComM2Float.toFixed(0).replace(/\B(?=(\d{3})+(?!\d))/g, '.');

    const diffPorcentual = ((parseFloat(valM2Parsed) / valComM2Float) * 100).toFixed(2)

    console.log(`El valor por metro cuadrado (${valM2}) es un ${diffPorcentual}% del valor comercial por metro cuadrado ($${valComM2FloatParsed}) (${valComM2})`);

    return {manzana, predio, rol, ubicacion, destino, reavaluo, avaluoTotal, avaluoAfecto, avaluoExento, codAreaHomo, rangoSupPred, valM2, valComM2, valComM2FloatParsed, diffPorcentual}
}
