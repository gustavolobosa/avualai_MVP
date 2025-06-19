const { chromium } = require('playwright');

module.exports = async function bot_TGR(page, manzana, predio, comuna, region) {

    await page.waitForSelector('//*[@id="tgr-sp-contenedor-iframe"]/iframe');

    const iframeElement = await page.$('//*[@id="tgr-sp-contenedor-iframe"]/iframe');
    const frame = await iframeElement.contentFrame();
    
    await frame.waitForSelector('#region');
    await frame.selectOption('#region', { label: region });

    await frame.waitForSelector('#comunas');
    await frame.selectOption('#comunas', { label: comuna });

    await frame.fill('//*[@id="rol"]', manzana);
    await frame.fill('//*[@id="subrol"]', predio);

    await frame.click('//*[@id="btnRecaptchaV3"]');

    await frame.waitForSelector('//*[@id="example_length"]/label/select');
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
}