# Load data from Salesforce to Datalake
## Create a new account in Salesforce
1.Click on the URL https://www.salesforce.com/in/form/signup/freetrial-sales/  
2.fill out the required information in the registration form, and then click on the "Start My Free Trial" button.

  ![image](https://github.com/user-attachments/assets/fbd3ec41-2133-4f97-b5fd-ea48051b648c)

3.Upon successfully creating a Salesforce account, you will receive a unique URL to your email address.
It is important to save this URL for future reference and easy access to your Salesforce account. 

4.Login Salesforce account >> Create a New Lead or record >>  Click on the New button

  ![image](https://github.com/user-attachments/assets/daf5d200-2bbf-4f73-84c0-8b77fa448c26)

5.Fill out the required information >> click on the save button

  
## Create a New Pipeline

1.Go to app.powerbi.com > Click on **Power BI** > Click on **Data Factory**

  ![image](https://github.com/user-attachments/assets/fbbe7bec-c280-44cf-b90c-2b88b3af23c8)

2.Click on new pipeline > name the pipeline pipeline_1

3.Click on the pipeline Activity and Select Copy Data Activity

  ![image](https://github.com/user-attachments/assets/ca6f4ef6-9578-4a32-abc1-d18a7bc1635a)


## Source 
1.Click on Source tab

  ![image](https://github.com/user-attachments/assets/8ce44e6d-03c9-4c36-9068-2333008b1f9c)

2.Select connection as more >> Select Data source as Salesforce objects

  ![image](https://github.com/user-attachments/assets/5caeb9ba-399b-4450-950b-035a3495fd4a)

3.Locate the Salesforce new account URL in your email inbox and copy it. Then, paste this URL into the 
  designated field labeled "Connection Name" on the relevant platform.

  
## Destination
1.Click on Destination tab

  ![image](https://github.com/user-attachments/assets/5fe09ca5-6837-489c-b993-c3f91bed75f8)

2.Select connection as more >> Select Destination as Lakehouse

  ![image](https://github.com/user-attachments/assets/c90a3fc7-52cb-4307-8944-d62d025fec01)

3.Select workspace as My workspace >> Name as Salesforce_record

  ![image](https://github.com/user-attachments/assets/75113d08-a1d9-42a6-9890-9ccd8041299e)

4.Select table option >> Create a New table >> Name as Sales_table1

  ![image](https://github.com/user-attachments/assets/a7ef1981-2059-4f21-b6b4-df825c0cd765)
  
5.Run the pipeline

 ![image](https://github.com/user-attachments/assets/120b9675-5d24-4afe-9ed1-4b314abd427f)
 
## Verify Data in Datalake
1. Select My workspace 

   ![image](https://github.com/user-attachments/assets/dba4a335-5be3-4e83-96df-b5ef2babb7ad)

2. Select Salesforce_record(Datalake) 

   ![image](https://github.com/user-attachments/assets/f5335743-844d-47d8-ad20-6a957940d628)

 
3. Observe the Data in table(Sales_table1).

   ![image](https://github.com/user-attachments/assets/b7a5444b-d4a4-4fb4-b446-e901377ab7d4)



