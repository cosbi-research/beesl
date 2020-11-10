#!/bin/bash

if [ $# -ne 4 ]; then
    echo
    echo "Execute from beesl project home. Exactly 4 args are required:"
    echo "  arg1 = model json path"
    echo "  arg2 = training data json path"
    echo "  arg3 = validation folder path"
    echo "  arg4 = testing file path"
    echo 
    echo "Multiple training data and models can be given separated by ':'"
    echo
    echo "Eg1 ./run_training.sh config/cosbi-biobert-base-params.json              \\"
    echo "                      config/base-genia.json                             \\"
    echo "                      data/corpora/GE11/dev"
    echo "                      data/GE11/not-masked/dev.mt.1                      \\"
    echo "Eg2 ./run_training.sh conf/bert.json:conf/MSbert.json:conf/scibert.json  \\"
    echo "                      conf/genia.json:conf/epi.json                      \\"
    echo "                      data/corpora/GE11/dev"
    echo "                      data/GE11/not-masked/dev.mt.1                      \\"
    echo "Experiment names will be auto-named as 'model_training_testing'"
	echo
    echo "REMEMBER: Activate env with 'conda activate beesl-env' prior to execution"

    exit 1
fi

IFS=':' read -r -a models <<< "$1"
IFS=':' read -r -a traindata <<< "$2"
validationdir="$3"
testfile="${4##*/}"

for train in "${traindata[@]}"; do
	trainfile="${train##*/}"
	trainfile="${trainfile%%.*}"
	
	for model in "${models[@]}"; do
		modelfile="${model##*/}"
		modelfile="${modelfile%%.*}"
		
		name="${modelfile}_${trainfile}_${testfile}"

		# Run training
		python train.py --name ${name} --dataset_config ${train} --parameters_config ${model} --device 0

		tstamp=`ls ~/beesl/logs/${name} | sort -k 2 | tail -1`
		
		# Deflatten and evaluate
		python predict.py logs/${name}/${tstamp}/model.tar.gz ${testfile} logs/${name}/${tstamp}/pred.txt --device 0
		python bio-mergeBack.py logs/${name}/${tstamp}/pred.txt ${testfile} 2 > logs/${name}/${tstamp}/pred-notmasked.txt
		python bioscripts/postprocess.py --filepath logs/${name}/${tstamp}/pred-notmasked.txt && mv output logs/${name}/${tstamp}/
		perl bioscripts/eval/a2-normalize.pl -v -g ${validationdir} -o logs/${1}/${tstamp}/output_norm logs/${1}/${tstamp}/output/*.a2
		perl bioscripts/eval/a2-evaluate.pl -g ${validationdir} -t1 -sp logs/${name}/${tstamp}/output_norm/*.a2 > logs/${name}/${tstamp}/results.txt
		
		mv ~/beesl/logs/${name}/${tstamp}/results.txt ~/beesl/logs/${name}/${tstamp}/results_${name}_${tstamp}.txt
		mv ~/beesl/logs/${name}/${tstamp}/metrics.txt ~/beesl/logs/${name}/${tstamp}/metrics_${name}_${tstamp}.txt

		# Copy data where needed, eg, an AWS bucket
		aws s3 cp ~/beesl/logs/${name}/${tstamp}/results_${name}_${tstamp}.txt s3://cosbi-beesl
		aws s3 cp ~/beesl/logs/${name}/${tstamp}/metrics_${name}_${tstamp}.txt s3://cosbi-beesl
	done
done
   
# Post training actions, eg, containers, shutdown, etc.
#sudo halt 
