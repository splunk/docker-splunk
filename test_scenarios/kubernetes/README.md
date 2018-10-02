# Splunk Docker Images on Kubernetes

### Getting Started

* You will require access to a Kubernetes Cluster. Some options include:

```
Docker for Mac: https://docs.docker.com/docker-for-mac/
EKS walkthrough: https://www.splunk.com/blog/2018/07/19/splunk-connect-for-kubernetes-on-eks.html
Minikube: https://kubernetes.io/docs/tasks/tools/install-minikube/
Heptio AWS Quickstart: https://aws.amazon.com/quickstart/architecture/heptio-kubernetes/
Openshift AWS Quickstart: https://aws.amazon.com/quickstart/architecture/openshift/
```
NOTE: Running complex deploys on docker for mac or minikube will make your laptop hot and slow and is more suited for actual clusters like the ones mentioned in the eks and AWS quickstarts. 

* Images

Pull the latest docker image into your environment using ```docker pull splunk/splunk:latest```

The example yamls are configured to pull from ```splunk/splunk:latest```. Ensure to update the image location if you are going to be pulling from a different repo. 

* Namespace

This deployment assumes you are deploying to a namespace called ```splunk```. If you would like to change the namespace, you can update the kubectl commands or update the yamls to include the namespace. You will also need to update the ```dnsConfig`` for the statefulsets accordingly:

``` 
dnsPolicy: ClusterFirst
      dnsConfig:
        searches:
          - indexer.splunk.svc.cluster.local
```

Where the search domain would consist of ```indexer.yourNamespace.svc.cluster.local``` 

See https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/#pod-identity for more info on statefulset identities/DNS. 

### NGINX

The new Splunk Docker image contains logic that allows your default.yml and license files to be centrally served via url. 

To demonstrate this capability, Nginx will be used to host our defaults.yml and our license.

Assuming you have pulled splunk:latest successfully, you can navigate to the ```nginx-data-www``` folder and use the following command to generate a sample default.yml

```docker run splunk/splunk:latest create-defaults > ./default.yml```

Once you have generated your default.yaml and inserted your license XML into the mySplunkLicense.lic file, it should look something like this: 

```
cd nginx-data-www/
ls -la
total 16
drwxr-xr-x  4 mmodestino  staff   128 Sep 26 23:50 .
drwxr-xr-x  5 mmodestino  staff   160 Sep 26 22:35 ..
-rw-r--r--  1 mmodestino  staff  1443 Sep 26 18:18 mySplunkLicense.lic
-rw-r--r--  1 mmodestino  staff   856 Sep 26 23:50 default.yml
```

Then, from the nginx directory create your configmaps:

```kubectl -n splunk create configmap nginx-data-www --from-file=nginx-data-www```

Then create one for the sample nginx conf file:

```kubectl -n splunk create configmap nginx-config --from-file=nginx-static.conf```

The deploy the nginx manfests:

```kubectl -n splunk apply -f manifests```


### 3idx1sh1cm

Return to the ```../test_scenarios/kubernetes``` folder and run the manifests:

```kubectl -n splunk apply -f 3idx1sh1cm```

This folder deploys a Cluster Master, 3 clustered Indexers and a single Search Head. 

```
$ kubectl -n splunk get pods

NAME                      READY     STATUS    RESTARTS   AGE
indexer-0                 1/1       Running   0          2m
indexer-1                 1/1       Running   0          2m
indexer-2                 1/1       Running   0          2m
master-55c7bcf764-8z5cj   1/1       Running   0          2m
search-6cb9945dbf-kbcfz   1/1       Running   0          2m

```

Once deployed, you can scale the indexing tier by using the command, ```kubectl scale statefulsets <stateful-set-name> --replicas=<new-replicas>```

To scale the Search Heads, you can use the command, ```kubectl scale deployment <deployment-name> --replicas=3```. This will add 2 more standalone Search Heads to the cluster.

To delete the deployments, run ```kubectl delete -f 3idx3sh1cm```

You could also run ```kubectl -n splunk delete statefulset <statefulset-name>``` or ```kubectl -n splunk delete deployment <deployment-name>```

### 3idxic3shc1cm1lm1dep 

To deploy this architecture run ```kubectl -n splunk apply -f 3idxc3shc1cm1lm1dep``` from the kubernetes directory. 

This folder of manifests will deploy a License Master, a Cluster Master, 3 clustered Indexers, 3 clustered Search Heads and a deployer. 

The manifests currently use emptyDir mounts but can easly be switched to use persistent volume claims to allow a user to persist data and configs. (examples to be added later)

```
$ kubectl -n splunk get pods

NAME                              READY     STATUS    RESTARTS   AGE
captain-7dc78ccf7f-ghjk8          1/1       Running   0          24s
deployer-9f6d7cf8c-q8c7f          1/1       Running   0          27s
indexer-0                         1/1       Running   0          26s
indexer-1                         1/1       Running   0          20s
indexer-2                         1/1       Running   0          13s
license-master-564cf888b5-ssp8b   1/1       Running   0          26s
master-5dcdd7b965-httjq           1/1       Running   0          25s
search-0                          1/1       Running   0          24s
search-1                          1/1       Running   0          16s

```

Once deployed, you can scale the search tier or indexing tier by using the command, ```kubectl -n splunk scale statefulsets <stateful-set-name> --replicas=<new-replicas>```

While the Master is a deployment resource and has the ability to be scaled, there is only ever one Master in today's Splunk (active with Hot standnby is the DR pattern), so while you COULD scale the master replicas, it makes no sense to at this time.  


### Kubernetes Resources:

https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/

https://kubernetes.io/docs/concepts/workloads/controllers/deployment/

https://kubernetes.io/docs/concepts/services-networking/service/


### Kubernetes Tips:

* Use ```kubectl -n splunk logs -f <podname>``` to watch for the Ansible plays to finish. 
* Once completed, you can then use ```kubectl -n splunk port-forward <podname> 9999:8000``` then visit ```localhost:9999``` in your browser to reach splunkweb on your instance.
* https://kubernetes.io/docs/reference/kubectl/cheatsheet/

### Other useful commands:

export kubeconfig environment variable from current directory - ```export KUBECONFIG=$(pwd)/<your-kubeconfig>```

show pods in the splunk name space with wide output - ```kubectl -n splunk get pods -o wide```

show your deployments - ```kubectl -n splunk get deployments```

sho your statefulsets - ``` kubectl -n splunk get statefulsets```

get service endpoints and external ip when using load balancers - ```kubectl -n splunk get svc -o wide```

describe your pod - ```kubectl -n splunk describe pod <podname>```

view the configmap the new containers require at startup - ```kubectl -n splunk describe configmap splunk-defaults```

