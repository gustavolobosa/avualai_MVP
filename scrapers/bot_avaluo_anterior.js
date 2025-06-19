const path = require('path');
const fs = require('fs');
const { execSync } = require('child_process');

module.exports = async function bot_SII_maps(page, variables, manzana, predio) {
    const downloadPath = path.resolve(__dirname, 'descargas'); // Carpeta donde guardar

    if (!fs.existsSync(downloadPath)) {
        fs.mkdirSync(downloadPath, { recursive: true });
    }

    // presionar el check del boton
    await page.waitForSelector('//*[@id="tablaSC"]/div/table/tbody/tr[3]/td[1]/div/label', { state: 'attached' });
    await page.locator('xpath=//*[@id="tablaSC"]/div/table/tbody/tr[3]/td[1]/div/label').click({ force: true });

    const anioActual = new Date().getFullYear();
    primeraVez = true

    for (let year = anioActual - 5; year < anioActual; year++) {
        for (let semestre of ['1', '2']) {

            // esperar a que se cargue la opcion de año
            await page.waitForSelector('select[name="añoCertifAnt"]', { state: 'attached' });
            await page.selectOption('select[name="añoCertifAnt"]', String(year));

            await page.waitForSelector('select[name="semestreCertifAnt"]', { state: 'attached' });
            await page.selectOption('select[name="semestreCertifAnt"]', semestre);

            if (primeraVez == true){

                await page.click('#comunaR'); // Asegúrate de enfocar el campo primero
                await page.type('#comunaR', variables.comuna, { delay: 10 }); // 100 ms entre letras

                await page.fill('#rolR', manzana);
                await page.fill('#nroR', predio);

                await page.waitForTimeout(1000);

                await page.click('#Rol');

                primeraVez = false
            }

            // presionar el check del boton para seleccionar la propiedad en la tabla de mas abajo
            await page.waitForSelector('//*[@id="tablaSC"]/div/table/thead/tr/th[1]/div/input', { state: 'attached' });
            await page.locator('//*[@id="tablaSC"]/div/table/thead/tr/th[1]/div/input').click({ force: true });

            await page.click('xpath=//*[@id="botonContainer"]/button[2]');

            // check otra institucion
            await page.waitForSelector('#checkOtraInstitucionD', { state: 'visible' });
            await page.locator('//*[@id="checkOtraInstitucionD"]').click({ force: true });

            await page.waitForSelector('#NombreInstitucionD', { state: 'attached' });
            await page.fill('#NombreInstitucionD', 'institucion de las instituciones');

            await page.fill('#MotivoTxtD', 'Estudio avaluo de valor anterior de la propiedad.');

            const fileName = `certificado_aval_ant_${year}_${semestre}.pdf`;

            // Esperar la descarga y hacer clic en el botón
            const [ download ] = await Promise.all([
                page.waitForEvent('download'),
                page.click('xpath=//*[@id="DescargaModal"]/div/div/div/form/div[8]/button[2]')
            ]);

            // Guardar el archivo con el nombre que tú quieras
            await download.saveAs(path.join(downloadPath, fileName));
            console.log(`✅ Descargado: ${fileName}`)

            await page.click('//div/div/div[6]/button[1]');


        }
    }

    try {
        const archivosPDF = fs.readdirSync(downloadPath)
            .filter(file => file.endsWith('.pdf'))
            .map(file => `"${path.join(downloadPath, file)}"`); // Comillas por espacios

        if (archivosPDF.length === 0) {
            console.log('⚠️ No se encontraron archivos PDF en la carpeta de descargas.');
            return;
        }

        const scriptPath = path.join(__dirname, 'readPDF.py');
        const command = `python "${scriptPath}" ${archivosPDF.join(' ')}`;
        const output = execSync(command, { encoding: 'utf-8' });
        console.log('📊 Resultados del análisis de PDFs:');
        console.log(output.trim());
    } catch (error) {
        console.error('❌ Error ejecutando el script Python:', error.message);
        console.error('Salida de error:', error.stderr);
    }

}