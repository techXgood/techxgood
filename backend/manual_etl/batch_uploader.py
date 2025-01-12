import csv
import json


# Input and output file paths
input_csv = "crawled_projects.csv"  # Input CSV file
projects_file = "../../data/projects.json"
output_file = projects_file       # Output JSON file

# Open and process the CSV file
with open(projects_file, mode="r", encoding="utf-8") as file:
    data = json.load(file)

# Open and process the CSV file
with open(input_csv, mode="r", encoding="utf-8") as file:
    reader = csv.DictReader(file, delimiter=';')  # Automatically reads the header
    for row in reader:
        print(row)
        new_obj = {
            "repo": row["GitHub URL"],
            "category": row["Category"],
            "image": row["Preview Image"],
        }
        data.append(new_obj)  # Convert each row to a dictionary and append

# Save the list of dictionaries to a file
with open(output_file, mode="w", encoding="utf-8") as json_file:
    json.dump(data, json_file, indent=4)

# Remove input file

print(f"Data saved to {output_file}.")
