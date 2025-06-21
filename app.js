const express = require('express');
const app = express();
const path = require('path');
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));


// Middleware to parse form data
app.use(express.urlencoded({ extended: true }));

// Serve static files
app.use(express.static('public'));

// Import your scrapers
const runScrapers = require('./scrapers/main');

// Form submission endpoint
app.post('/run-scrapers', (req, res) => {
    const { comuna, region, direccion, numero } = req.body;
    
    // Execute scrapers with form data
    runScrapers({ comuna, region, direccion, numero })
        .then(result => {
            res.render('result', { result });
        })
        .catch(error => {
            res.status(500).send(`Error: ${error.message}`);
        });
});

// Start server
const PORT = 3000;
app.listen(PORT, () => {
    console.log(`Server running at http://localhost:${PORT}`);
});
