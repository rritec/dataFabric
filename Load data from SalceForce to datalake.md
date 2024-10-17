# Load data from Salesforce to Datalake
## 1.Create a new account in Salesforce
* click on the URL https://www.salesforce.com/in/form/signup/freetrial-sales/  > fill out the required information in the registration form, and then click on the "Start My Free Trial" button.

  ![image](https://github.com/user-attachments/assets/fbd3ec41-2133-4f97-b5fd-ea48051b648c)

* Upon successfully creating a Salesforce account, you will receive a unique URL to your email address. It is important to save this URL for future reference and easy access to your Salesforce account. 

* Login Salesforce account >> Create a New Lead or record >>  Click on the New button
  
  ![image](https://github.com/user-attachments/assets/250cb9b7-8047-4321-a916-a5cab239ec08)

* Fill out the required information >> click on the save button
## 2. Create a New Pipeline
* Go to app.powerbi.com > Click on **Power BI** > Click on **Data Factory**
  
![image](https://github.com/user-attachments/assets/b104cc60-1610-4638-9a45-78ed940dc634)

* Click on new pipeline > name the pipeline pipeline_1
* Click on the pipeline Activity and Select Copy Data Activity
   ![image](https://github.com/user-attachments/assets/70b6157d-987b-4c84-a640-9c671811700b)
  
* Click on Source tab > Select Connection as more >> Select Data source as Salesforce objects
  ![image](https://github.com/user-attachments/assets/b3219937-4128-45c9-b827-c3466d6b0967)

* Locate the Salesforce new account URL in your email inbox and copy it. Then, paste this URL into the designated field labeled "Connection Name" on the relevant platform.

* Click on Destination tab >


## 3. Verify Data in Datalake
