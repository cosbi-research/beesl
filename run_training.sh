#!/bin/bash

# From beesl project home type:
# ./run_training.sh "EXPERIMENT_NAME" config/base-genia.json config/cosbi-biobert-base-params.json

#param $1 = experiment name, same name will be placed on the logs/ folder
#param $2 = configuration file for data for training
#param $3 = configuration file for the bert model and network parameters

if [ $# -ne 3 ]; then
    echo "Exactly 3 args are required: arg1=name, arg2=training data json path, arg3=model json path"
    echo "Multiple training data and models can be given separated by ':', exp name will be auto-renamed"
    echo "Ex1 ./run_training.sh 'EXPERIMENT_NAME' config/base-genia.json config/cosbi-biobert-base-params.json"
    echo "Ex2 ./run_training.sh 'EXP' conf/genia.json:conf/epi.json conf/bert.json:conf/MSbert.json:conf/scibert.json"
    echo "REMEMBER: Activate environment with 'conda activate beesl-env'"

    exit 1
fi

IFS=':' read -r -a traindata <<< "$2"
IFS=':' read -r -a models <<< "$3"
    
for train in "${traindata[@]}"; do
	trainfile="${train##*/}"
	trainfile="${trainfile%%.*}"
	
	for model in "${models[@]}"; do
		modelfile="${model##*/}"
		modelfile="${modelfile%%.*}"
		
		name="${1}_${trainfile}_${modelfile}"
		# Run training
		python train.py --name ${name} --dataset_config ${train} --parameters_config ${model} --device 0 > out.txt

		tstamp=`ls ~/beesl/logs/$1 | sort -k 2 | tail -1`
		mv ~/beesl/logs/${1}/${tstamp}/results.txt ~/beesl/logs/${1}/${tstamp}/results_${name}_${tstamp}.txt
		mv ~/beesl/logs/${1}/${tstamp}/metrics.txt ~/beesl/logs/${1}/${tstamp}/metrics_${name}_${tstamp}.txt

		# Copy data to AWS bucket
		aws s3 cp ~/beesl/logs/${1}/${tstamp}/results_${name}_${tstamp}.txt s3://cosbi-beesl
		aws s3 cp ~/beesl/logs/${1}/${tstamp}/metrics_${name}_${tstamp}.txt s3://cosbi-beesl
	done
done
   
# shutdown
#sudo halt 
    