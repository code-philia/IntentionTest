var express = require("express");
var router = express.Router();

router.get("/get_all_jsons", function(req, res, next) {
    // Save the list of all json files in the dataset_reorganised folder
    var fs = require("fs");
    var path = require("path");

    const {globSync} = require("glob")

    const allJsons = globSync('**/*.json', {cwd: "dataset_reorganised"});
    
    res.send(allJsons.map(x => "../dataset_reorganised/" + x))
});

router.post("/get_data", function(req, res, next) {
    // Read from a local file ../dataset_reorganised/itext-java/barcodes.json
    var fs = require("fs");
    var path = require("path");

    var jsonPath = req.body.jsonPath;
    
    fs.readFile(path.join(__dirname, jsonPath), "utf8", function(err, data) {
        if (err) {
            console.log(err);
        }
        data = JSON.parse(data);
        res.send(data);
    });
});

// a post request to update the file
router.post("/update_data", function(req, res, next) {
    var fs = require("fs");
    var path = require("path");

    var jsonPath = req.body.jsonPath;
    var data = req.body.data;

    fs.writeFile(path.join(__dirname, jsonPath), JSON.stringify(data), function(err) {
        if (err) {
            console.log(err);
        }
        res.send("File updated");
    });
});

module.exports = router;