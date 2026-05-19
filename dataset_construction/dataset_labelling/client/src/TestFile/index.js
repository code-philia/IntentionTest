import "./index.css";
import { useState } from "react";
import SyntaxHighlighter from 'react-syntax-highlighter';
import { docco } from 'react-syntax-highlighter/dist/esm/styles/hljs';

function TestFile({testFile, currTest, labelNoFocalMethod, data, focalFilePath, currTestIndex, labelLastLabel, manualLabel}) {
  const startLine = currTest && currTest[0];
  const endLine = currTest && currTest[1];
  const [showFullTest, setShowFullTest] = useState(true);
  return (
    <div className="test_file">
      <div className="horizontalFlex">
        <h3>Test Case</h3>
        <button onClick={() => labelNoFocalMethod()}>No Focal Method</button>
        <button onClick={() => labelLastLabel()}>Same w. Last Label </button>
        {manualLabel && <span style={{color: 'red'}}> Label manually please </span>}
      </div>
      {data && focalFilePath in data && "tests" in data[focalFilePath] && currTestIndex < data[focalFilePath]["tests"].length && "label" in data[focalFilePath]["tests"][currTestIndex] && 
          <span>Current Label: {data[focalFilePath]["tests"][currTestIndex]["label"]}</span>}
      <br/>
      {testFile && <SyntaxHighlighter language="java" theme={docco} wrapLongLines={true}>
        {testFile.slice(startLine, endLine).join('')}
      </SyntaxHighlighter>}
      <br/>
      <div className="horizontalFlex">
        <h4>Full test file</h4>
        <button onClick={() => setShowFullTest((prev) => !prev)}>Show full test</button>
      </div>
      {testFile && showFullTest && <SyntaxHighlighter language="java" theme={docco} wrapLongLines={true}>
        {testFile.join('')}
      </SyntaxHighlighter>}
    </div>
  );
  }
  
  export default TestFile;