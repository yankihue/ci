with open('poems_initial.json', 'r') as infile, \
        open('poems.json', 'w') as outfile:
    data = infile.read()
    data = data.replace("，", " ")
    data = data.replace("。", "")
    data = data.replace("？", "")

    outfile.write(data)
