const { chromium } = require('playwright');  // También puedes usar firefox o webkit
const readline = require('readline');
const path = require('path');
const fs = require('fs');

const bot_TGR = require('./bot_TGR'); // Asegúrate de que la ruta sea correcta
const mapping = require('./mapping');
const bot_SII_maps = require('./maps');
const bot_SII_rol = require('./bot_SII');
const bot_AA = require('./bot_avaluo_anterior');

module.exports = async function({ comuna, region, direccion, numero }) {

    console.log(`Running scrapers with: 
        Comuna: ${comuna}
        Region: ${region}
        Direccion: ${direccion}
        Numero: ${numero}`);

    // // Helper para hacer preguntas de forma asincrónica
    // const rl = readline.createInterface({
    //     input: process.stdin,
    //     output: process.stdout,
    // });

    // const askQuestion = (question) => {
    //     return new Promise((resolve) => {
    //     rl.question(question, (answer) => resolve(answer));
    //     });
    // };

    // // Pedir los inputs al usuario
    // // const variables = {
    // //     region: (await askQuestion('Ingrese la región: ')).toUpperCase(),
    // //     comuna: (await askQuestion('Ingrese la comuna: ')).toUpperCase(),
    // //     direccion: await askQuestion('Ingrese la dirección: '),
    // //     numero: await askQuestion('Ingrese el número: '),
    // // };

    const variables = {
        region: region,
        comuna: comuna,
        direccion: direccion,
        numero: numero,
    };


    // rl.close(); 
    // Lanzar el navegador
    const browser_SII = await chromium.launch({ headless: false }); // headless: true para no mostrar el navegador
    const page_SII = await browser_SII.newPage();

    // Ir a una página objetivo
    await page_SII.goto('https://www4.sii.cl/mapasui/internet/#/contenido/index.html');

    // Ejecutar el bot SII Maps
    await bot_SII_maps(page_SII, variables);

    // Ejecutar el bot SII Rol y obtener la manzana y predio
    const { manzana, 
        predio, 
        rol, 
        ubicacion, 
        destino, 
        reavaluo, 
        avaluoTotal, 
        avaluoAfecto, 
        avaluoExento, 
        codAreaHomo, 
        rangoSupPred, 
        valM2, 
        valComM2, 
        valComM2FloatParsed, 
        diffPorcentual } = await bot_SII_rol(page_SII, variables);

    await browser_SII.close();

    const browser_TGR = await chromium.launch({ headless: false }); // headless: true para no mostrar el navegador
    const page_TGR = await browser_TGR.newPage();

    // Ir a una página objetivo
    await page_TGR.goto('https://www.tgr.cl/tramites-tgr/certificado-de-movimientos-de-contribuciones/');
    
    // Ejecutar el bot TGR
    const {vencidas, proximas} = await bot_TGR(page_TGR, manzana, predio, mapping[variables.comuna], variables.region);

    await browser_TGR.close();

    const browser_AA = await chromium.launch({ headless: false }); // headless: true para no mostrar el navegador
    const page_AA = await browser_AA.newPage();

    // Ir a una página objetivo
    await page_AA.goto('https://www2.sii.cl/vicana/Menu/ConsultarAntecedentesSC');

    const graficoPDF = await bot_AA(page_AA, variables, manzana, predio);
    console.log("📊 Datos del gráfico PDF:", graficoPDF);

    await browser_AA.close();

    return {
        rol,
        ubicacion,
        destino,
        reavaluo,
        avaluoTotal,
        avaluoAfecto,
        avaluoExento,
        codAreaHomo,
        rangoSupPred,
        valM2,
        valComM2,
        vencidas,
        proximas, 
        valComM2FloatParsed, 
        diffPorcentual,
        graficoPDF
    };

}