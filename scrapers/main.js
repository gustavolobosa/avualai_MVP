const { chromium } = require('playwright');  // También puedes usar firefox o webkit
const readline = require('readline');
const path = require('path');
const fs = require('fs');

const bot_TGR = require('./bot_TGR'); // Asegúrate de que la ruta sea correcta
const mapping = require('./mapping');
const bot_SII_maps = require('./maps');
const bot_SII_rol = require('./bot_SII');
const bot_AA = require('./bot_avaluo_anterior');
const bot_SII_comparar = require('./bot_SII_comparar');



async function reintentarBotConBrowser(fnFactory, nombre = 'bot', intentosMax = 5, esperaMs = 2000) {
    for (let intento = 1; intento <= intentosMax; intento++) {
        const browser = await chromium.launch({ headless: false });
        const page = await browser.newPage();
        try {
            console.log(`🔄 Ejecutando ${nombre} (intento ${intento}/${intentosMax})`);
            const resultado = await fnFactory(page);
            await browser.close();
            console.log(`✅ ${nombre} completado`);
            return resultado;
        } catch (err) {
            console.error(`❌ Error en ${nombre}: ${err.message}`);
            await browser.close();
            if (intento < intentosMax) {
                console.log(`⏳ Reintentando en ${esperaMs} ms...`);
                await new Promise(res => setTimeout(res, esperaMs));
            } else {
                throw new Error(`Fallo en ${nombre} después de ${intentosMax} intentos.`);
            }
        }
    }
}



module.exports = async function({ comuna, region, direccion, numero }) {
    // agrega el codigo de la comuna obtenido del ../datos/mapping.json al console.log
    const codigos_comunas = JSON.parse(fs.readFileSync(path.join(__dirname, '../datos/mapping.json'), 'utf-8'));
    const datos_prediales = JSON.parse(fs.readFileSync(path.join(__dirname, '../datos/datos_por_predio_LAS_CONDES.json'), 'utf-8'));
    console.log(`Datos prediales cargados: ${Object.keys(datos_prediales).length} entradas.`);
    const codigoComuna = codigos_comunas[comuna] || 'Desconocido';

    console.log(`Running scrapers with: 
        Comuna: ${comuna} (Código: ${codigoComuna})
        Region: ${region}
        Direccion: ${direccion}
        Numero: ${numero}`);

    const variables = {
        region: region,
        comuna: comuna,
        direccion: direccion,
        numero: numero,
        codigoComuna: codigoComuna,
    };

    const {
        manzana, predio, rol, ubicacion, destino,
        reavaluo, avaluoTotal, avaluoAfecto, avaluoExento,
        codAreaHomo, rangoSupPred, valM2, valComM2,
        valComM2FloatParsed, diffPorcentual
    } = await reintentarBotConBrowser(
        async (page) => {
            await page.goto('https://www4.sii.cl/mapasui/internet/#/contenido/index.html');
            await bot_SII_maps(page, variables);
            return await bot_SII_rol(page, variables);
        },
        'SII Maps + Rol'
    );

    //ejecuta el bot_SII_rol con todas las propiedades de la manzana que corresponderian a todos los valores del datos_prediales que tengan la manzana y la comuna, el valor de la llave del json de datos_prediales es predio-manzana-comuna
    const predios = Object.keys(datos_prediales).filter(key => {
        const [p, m, c] = key.split('-');
        return m === manzana && c === codigoComuna;
    });

    console.log(`Encontrados ${predios.length} predios para la manzana ${manzana} en la comuna ${comuna}.`);
    console.log(`Predios: ${predios.join(', ')}`);
    //una lista para ir guardando los resultados de cada predio
    const resultadosPredios = [];
    for (const predio_com of predios) {
        predio_actual = predio_com.split('-')[0].trim();
        console.log(`Procesando predio: ${predio_actual}`);
        const { avaluoTotal, direccion
        } = await reintentarBotConBrowser(
            async (page) => {
                await page.goto('https://www4.sii.cl/mapasui/internet/#/contenido/index.html');
                return await bot_SII_comparar(page, predio_actual, manzana, variables);
            },
            'SII comparar Rol'
        );
        resultadosPredios.push({ predio: predio_actual, avaluoTotal, direccion });
    }

    console.log(`Resultados de los predios:`);
    resultadosPredios.forEach(({ predio, avaluoTotal, direccion }) => {
        console.log(`Predio: ${predio}, Avaluo Total: ${avaluoTotal}, Direccion: ${direccion}`);
    });

    const [tgrData, graficoPDF] = await Promise.all([
        reintentarBotConBrowser(
            async (page) => {
                await page.goto('https://www.tgr.cl/tramites-tgr/certificado-de-movimientos-de-contribuciones/');
                return await bot_TGR(page, manzana, predio, mapping[variables.comuna], variables.region);
            },
            'bot_TGR'
        ),
        reintentarBotConBrowser(
            async (page) => {
                await page.goto('https://www2.sii.cl/vicana/Menu/ConsultarAntecedentesSC');
                return await bot_AA(page, variables, manzana, predio);
            },
            'bot_AA'
        )
    ]);

    // Desestructurar datos de TGR
    const { vencidas, proximas } = tgrData;

    console.log("📊 Datos del gráfico PDF:", graficoPDF);


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
        graficoPDF,
        resultadosPredios,
        predio
    };

}