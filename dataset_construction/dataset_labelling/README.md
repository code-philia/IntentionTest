# README

This is a very simple web app to help with the dataset labelling process. Looks and efficiency are not our priority, just functionality.

## How to run the program

Prerequisite: npm installed

```
# Change directory to api dir
cd api
# Install and run
npm install
npm start

# On another terminal, run the client
cd client
npm install
npm start
```

## Brief overview

Go to localhost:3000, you should see something like this:

![image](https://github.com/bernarduskrishna/dataset_labelling/assets/77195969/d7cb1499-dbc9-4e6c-b4e0-9633f41d2c9f)

The right side shows the current test

The left side shows the focal file, together with the coverage

- Select JSON will allow you to change the module whose data we want to label
  
  ![image](https://github.com/bernarduskrishna/dataset_labelling/assets/77195969/d8ba031d-0f44-4b38-b1d2-32a50adce2a1)
  
- Select Focal File will allow you to change the focal file within the module whose data we want to label
  
  ![image](https://github.com/bernarduskrishna/dataset_labelling/assets/77195969/60789a9d-c0f0-47ea-8a4b-99ddabb28157)
  
  Red means that the focal file still has tests we have not labelled
- This part allows you to navigate through the tests that are subjected to the focal file

  Alternatively, use "q" and "w" to go to the previous and next test respectively (refer to the "Shortcuts" section at the bottom)
  
  ![image](https://github.com/bernarduskrishna/dataset_labelling/assets/77195969/5b9516dc-f838-44a3-9eec-08859d25d601)

## How to label
- Click on any line that is covered (indicated by pale yellow highlighter) from the method you think is the focal method

  OR press "e" to label with the latest label you gave (refer to the "Shortcuts" section at the bottom)
  
  ![image](https://github.com/bernarduskrishna/dataset_labelling/assets/77195969/3140dc49-edda-4903-97d3-19aa2a2d5041)
  
  After you click it, the label should appear beside the "Test Case" text:

  ![image](https://github.com/bernarduskrishna/dataset_labelling/assets/77195969/d0386765-4d33-438b-8ce4-2f2ff738dbef)
  
  Note: we only allow clicking on highlighted lines because a focal method MUST be covered by the test, or else it doesn't make sense
- Sometimes, the test might be an integration test, or the automated script fails to get the appropriate focal file. In that case, just label the data as No Focal Method
  
  ![image](https://github.com/bernarduskrishna/dataset_labelling/assets/77195969/3fb5e0dd-40c2-4f97-8306-522b19aa19aa)
  
- Sometimes, after clicking the highlighted line, the following label appears instead of what you think is the focal method:
  
  ![image](https://github.com/bernarduskrishna/dataset_labelling/assets/77195969/c0a7ca2a-aa38-42ee-a7c3-827f65ffdf37)
  
  This happens whenever you click on a line that is not within a method OR you click on a line that is within a constructor (we do not support constructor labelling for now) OR the method failed to be resolved by the javaparser library during the preprocessing process. It's totally fine, just keep the label as is.
- Sometimes, you label a data point, but when you come back the next time, the label is gone (this is usually the last thing you label). This is a known bug that I have yet to resolve. But just click the label twice and it should register haha.

## Shortcuts

q -> previous test

w -> next test

e -> same label as the last label (last label we manually give, not the label of the previous test)



