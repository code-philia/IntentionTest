import './App.css';
import FocalFile from './FocalFile';
import TestFile from './TestFile';
import React, { useEffect, useState, useRef } from 'react';
import Dropdown from 'react-bootstrap/Dropdown';

function App() {
  const [jsonPathList, setJsonPathList] = useState([]);
  const [jsonPath, setJsonPath] = useState("../dataset_reorganised/itext-java/barcodes.json");
  const [latestLabel, setLatestLabel] = useState(null);
  const [manualLabel, setManualLabel] = useState(null);

  const [focalFileList, setFocalFileList] = useState([]);

  const [focalFilePath, setFocalFilePath] = useState("/bernard/dataset_construction/prep/repos/itext-java/barcodes/src/main/java/com/itextpdf/barcodes/Barcode39.java");
  const [currTestIndex, setCurrTestIndex] = useState(0);
  const [totalTests, setTotalTests] = useState(0);
  const [alreadyLabelled, setAlreadyLabelled] = useState(false);

  const [data, setData] = useState(null);
  const [focalFile, setFocalFile] = useState(null);
  const [testFile, setTestFile] = useState(null);

  const [currTest, setCurrTest] = useState(null);
  const [currCovLines, setCurrCovLines] = useState(null);

  const currCovLinesRef = useRef(currCovLines);

  const [reverse_method_lines_dict, setReverseMethodLinesDict] = useState(null);
  const [method_lines_dict, setMethodLinesDict] = useState(null);

  useEffect(() => {
    currCovLinesRef.current = currCovLines;
  }, [currCovLines])

  const label = (label) => {
    const methodName = label;

    setData((prevData) => {
      const new_data = {...prevData};
      new_data[focalFilePath]["tests"][currTestIndex]["label"] = methodName;

      return new_data;
    }, (() => {
      fetch("http://localhost:9000/testAPI/update_data", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({jsonPath: jsonPath, data: data})
      })
    })())
  }

  const labelLastLabel = () => {
    if (latestLabel && latestLabel in method_lines_dict) {
      // Check whether it's covered
      const start_end = method_lines_dict[latestLabel];
      const start = start_end[0];
      const end = start_end[1];

      for (let i = start; i < end; i++) {
        if (currCovLinesRef.current.includes(i)) {
          label(latestLabel);
          return;
        }
      }
    }

    if (latestLabel && latestLabel.slice(0, 2) == "<<") {
      label(latestLabel);
      return;
    }

    setManualLabel(true);
  }

  const labelNoFocalMethod = () => {
    setLatestLabel("<<NO FOCAL METHOD>>");

    label("<<NO FOCAL METHOD>>")
  }

  const label_w_line = (line) => {
    const methodName = line in reverse_method_lines_dict 
      ? reverse_method_lines_dict[line]
      : "<<UNRECOGNISED_METHOD>>";

    setLatestLabel(methodName);

    label(methodName);
  }

  useEffect(() => {
    fetch("http://localhost:9000/testAPI/get_data",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({jsonPath: jsonPath})
      }
    )
      .then(res => res.text())
      .then(res => JSON.parse(res))
      .then(res => {
        // setCurrTestIndex(0, (() => {setData(res)})());
        setCurrTestIndex(0);
        setFocalFilePath(Object.keys(res)[0], (() => {setData(res);})());
      });
  }, [jsonPath])

  useEffect(() => {
    fetch("http://localhost:9000/testAPI/get_all_jsons")
      .then(res => res.text())
      .then(res => JSON.parse(res))
      .then(res => setJsonPathList(res));
  }, [])

  useEffect(() => {
    if (data) {
      setManualLabel(false)
      setFocalFile(data[focalFilePath]["class_content"]);
      setTestFile(data[focalFilePath]["test_content"]);
      setReverseMethodLinesDict(data[focalFilePath]["reverse_method_lines_dic"]);
      setMethodLinesDict(data[focalFilePath]["method_lines_dic"]);
      setFocalFileList(Object.keys(data));
      setTotalTests(data[focalFilePath]["tests"].length);
      if (currTestIndex >= data[focalFilePath]["tests"].length) { return; }
      setCurrTest(data[focalFilePath]["tests"][currTestIndex]["test_lines"]);
      setCurrCovLines(data[focalFilePath]["tests"][currTestIndex]["covered_lines"])
      setAlreadyLabelled("label" in data[focalFilePath]["tests"][currTestIndex]);
    }
    const checkKey = (event) => {
      if (event.key === 'q') {
        setCurrTestIndex((prev) => prev == 0 ? prev : prev - 1);
      } else if (event.key === 'w') {
        setCurrTestIndex((prev) => prev == totalTests - 1 ? prev : prev + 1);
      } else if (event.key === 'e') {
        labelLastLabel()
      }
    };

    // Add event listener
    window.addEventListener('keydown', checkKey);

    // Remove event listener on cleanup
    return () => window.removeEventListener('keydown', checkKey);
  }, [data, focalFilePath, currTestIndex])

  useEffect(() => {
    setCurrTestIndex(0);
  }, [focalFilePath])

  return (
    <div className="App">
      <h3>Current JSON (Module): {jsonPath}</h3>
      <div className="horizontalFlex">
        {data && jsonPathList.length > 0 && <Dropdown>
          <Dropdown.Toggle variant="success" id="dropdown-basic">
            Select JSON
          </Dropdown.Toggle>
          <Dropdown.Menu>
            {jsonPathList.map((path) => {
              return <Dropdown.Item onClick={() => setJsonPath(path)}>{path}</Dropdown.Item>
            }
            )}
          </Dropdown.Menu>
        </Dropdown>}
        {data && focalFileList.length > 0 && <Dropdown>
          <Dropdown.Toggle variant="success" id="dropdown-basic">
            Select Focal File
          </Dropdown.Toggle>
          <Dropdown.Menu>
            {focalFileList.map((path) => {
              return <Dropdown.Item onClick={() => setFocalFilePath(path)} 
                style={{backgroundColor: (() => {
                  // If all tests are labelled, color it green, otherwise red
                  if (path in data && "tests" in data[path] && data[path]["tests"].map((test) => test["label"]).filter((label) => label != undefined).length == data[path]["tests"].length) {
                    return "green";
                  } else {
                    return "red";
                  }
                  })()}}>
                  {path}
              </Dropdown.Item>
            }
            )}
          </Dropdown.Menu>
        </Dropdown>}
        <span> Current focal file: {focalFilePath}</span>
      </div>
      
      <div className="horizontalFlex">
        <h3>Current test in file: {currTestIndex + 1}/{totalTests}</h3>
        <button onClick={() => setCurrTestIndex((prev) => prev == 0 ? prev : prev - 1)}>Previous Test</button>
        <button onClick={() => setCurrTestIndex((prev) => prev == totalTests - 1 ? prev : prev + 1)}>Next Test</button>
        {alreadyLabelled ? <h3 style={{color: 'green'}}>Already Labelled</h3> : <h3 style={{color: 'red'}}>Not Labelled Yet</h3>}
        <span style={{display: 'inline-flex', alignItems: "center"}}> All Tests: </span>
        {/* For each test index, make a button. If it's already labelled, color it green, otherwise red */}
        {data && focalFilePath in data && "tests" in data[focalFilePath] && data[focalFilePath]["tests"].length == totalTests && Array.from(Array(totalTests).keys()).map((index) => {
          return <span className="clickable" style={
            "label" in data[focalFilePath]["tests"][index] 
              ? {color: "green", display: 'inline-flex', alignItems: "center"}
                : {color: "red", display: 'inline-flex', alignItems: "center"}
          } onClick={() => setCurrTestIndex(index)}>{index + 1}</span>
        })}
      </div>
      <br/>
      <div className="horizontalFlex">
        <FocalFile focalFile={focalFile} currCovLines={currCovLines} label={label_w_line}/>
        <TestFile testFile={testFile} currTest={currTest} 
          labelNoFocalMethod={labelNoFocalMethod} data={data} focalFilePath={focalFilePath} currTestIndex={currTestIndex}
          labelLastLabel={labelLastLabel} manualLabel={manualLabel}
        />
      </div>
      
    </div>
  );
}

export default App;
