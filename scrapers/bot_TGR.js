const { chromium } = require('playwright');

module.exports = async function bot_TGR(page, manzana, predio, comuna, region) {

    console.log(`Running bot_TGR with:
        Manzana: ${manzana}
        Predio: ${predio}
        Comuna: ${comuna}
        Region: ${region}`);


    await page.waitForSelector('//*[@id="tgr-sp-contenedor-iframe"]/iframe');

    const iframeElement = await page.$('//*[@id="tgr-sp-contenedor-iframe"]/iframe');
    const frame = await iframeElement.contentFrame();

    console.log('Esperando a que el iframe esté listo...');


    // Seleccionar la región
    await frame.selectOption('#region', { label: region });
    console.log('Región seleccionada:', region);

    await frame.waitForTimeout(500);

    const disponibles = await frame.evaluate(() => {
        return Array.from(document.querySelectorAll('#comunas option')).map(opt => opt.label);
    });

    console.log('Comunas disponibles:', disponibles);

    // Seleccionar la comuna
    await frame.selectOption('#comunas', { label: comuna });
    console.log('Comuna seleccionada:', comuna);


    await frame.fill('//*[@id="rol"]', manzana);
    await frame.fill('//*[@id="subrol"]', predio);

    await frame.waitForSelector('#btnRecaptchaV3', {timeout: 5000})
    await frame.click('#btnRecaptchaV3');

    await frame.waitForSelector('//*[@id="example_length"]/label/select', {timeout: 5000});
    await frame.selectOption('//*[@id="example_length"]/label/select', '100');

    const datosVencidos = await frame.evaluate(() => {
        // Esperar a que la tabla esté completamente cargada
        const tabla = document.querySelector('#example');

        const filas = document.querySelectorAll('#example tbody tr');
        const hoy = new Date();

        console.log('Fecha de hoy:', hoy);
        console.log('Número de filas encontradas:', filas.length);


        const vencidas = [];
        const proximas = [];

        for (const fila of filas) {
            const celdas = fila.querySelectorAll('td');
            const fechaTexto = celdas[4]?.innerText.trim();
            const moneda = celdas[5]?.innerText.trim();
            const saldo = celdas[6]?.innerText.trim();

            if (fechaTexto && moneda && saldo) {
                const partesFecha = fechaTexto.split('-');
                const fecha = new Date(`${partesFecha[2]}-${partesFecha[1]}-${partesFecha[0]}`);

                if (fecha < hoy && saldo !== '0') {
                    vencidas.push({ vencimiento: fechaTexto, moneda, saldo });
                }

                if (fecha >= hoy && saldo !== '0') {
                    proximas.push({ vencimiento: fechaTexto, moneda, saldo });
                }
            }
        }

        //si proximas tiene mas de 1 elemento, quedarse con el mas reciente
        if (proximas.length > 1) {
            proximas.sort((a, b) => new Date(a.vencimiento) - new Date(b.vencimiento));
            proximas.splice(1); // Mantener solo el más reciente
        }

        return {vencidas, proximas};
    });

    console.log('Movimientos vencidos encontrados:');
    console.table(datosVencidos.vencidas);
    console.log('Proxima cuota:');
    console.table(datosVencidos.proximas);

    vencidas = datosVencidos.vencidas
    proximas = datosVencidos.proximas

    return {vencidas, proximas}
}


// if (require.main === module) {
//     (async () => {
//         const { chromium } = require('playwright');
//         const bot_TGR = module.exports;

//         const browser = await chromium.launch({ headless: false });
//         const page = await browser.newPage();

//         await page.goto('https://www.tgr.cl/tramites-tgr/certificado-de-movimientos-de-contribuciones/');

//         const result = await bot_TGR(
//             page,
//             '782',  // manzana
//             '9',    // predio
//             'LAS CONDES [71]', // comuna exacta como aparece en el <select>
//             'REGION METROPOLITANA DE SANTIAGO' // región exacta
//         );

//         console.log('📊 Resultado final:');
//         console.log(result);

//         await browser.close();
//     })();
// }
