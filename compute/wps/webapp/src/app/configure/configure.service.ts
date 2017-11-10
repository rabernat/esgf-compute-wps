import { Http, Headers, URLSearchParams } from '@angular/http';
import { Injectable } from '@angular/core';
import { Params } from '@angular/router';

import { Axis } from './axis.component';
import { Parameter } from './parameter.component';
import { WPSService, WPSResponse } from '../core/wps.service';

export interface Dataset {
  axes: Axis[];
  files: string[];
}

export interface SearchResult {
  [index: string]: Dataset;
}

export class RegridOptions {
  lats: number;
  lons: number;
}

export class Configuration {
  process: string;
  dataset: Dataset;
  variable: string;
  regrid: string;
  regridOptions: RegridOptions;
  params: Parameter[];

  // ESGF search parameters
  datasetID: string;
  indexNode: string;
  query: string;
  shard: string;

  constructor() {
    this.regrid = 'None';

    this.regridOptions = new RegridOptions();

    this.dataset = { axes: [], files: [] } as Dataset;

    this.params = [];
  }

  validate() { 
    if (this.dataset.axes === undefined) {
      throw 'Missing domain axes, wait until the domain has loaded';
    }

    if (this.regrid !== 'None') {
      if (this.regrid === 'Uniform') {
        if (this.regridOptions.lons === undefined) {
          throw `Regrid option "${this.regrid}" requires Longitude to be set`;
        }
      }

      if (this.regridOptions.lats === undefined) {
        throw `Regrid option "${this.regrid}" require Latitude to be set`;
      }
    }

    this.params.forEach((param: Parameter) => {
      if (param.key === '' || param.value === '') {
        throw 'Parameters are invalid';
      }
    });
  }

  prepareData(): string {
    let data = '';
    let numberPattern = /\d+\.?\d+/;

    this.validate();

    data += `process=${this.process}&`;

    data += `variable=${this.variable}&`;

    data += `regrid=${this.regrid}&`;

    if (this.regrid !== 'None') {
      data += `longitudes=${this.regridOptions.lons}&`;

      data += `latitudes=${this.regridOptions.lats}&`;
    }

    data += `files=${this.dataset.files}&`;

    let dimensions = JSON.stringify(this.dataset.axes.map((axis: Axis) => { return axis; }));

    data += `dimensions=${dimensions}&`;

    let parameters = this.params.map((param: Parameter) => { return `${param.key}=${param.value}`; }).join(',');

    data += `parameters=${parameters}`;

    return data;
  }
}

@Injectable()
export class ConfigureService extends WPSService {
  constructor(
    http: Http
  ) { 
    super(http); 
  }

  processes(): Promise<string[]> {
    return this.get('/wps/processes')
      .then(response => {
        return response.data;
      });
  }

  searchESGF(config: Configuration): Promise<SearchResult> { 
    let params = new URLSearchParams();

    params.append('dataset_id', config.datasetID);
    params.append('index_node', config.indexNode);
    params.append('query', config.query);
    params.append('shard', config.shard);

    return this.get('/wps/search', params)
      .then(response => {
        return response.data as SearchResult;
      });
  }

  searchVariable(config: Configuration): Promise<Axis[]> {
    let params = new URLSearchParams();

    params.append('dataset_id', config.datasetID);
    params.append('index_node', config.indexNode);
    params.append('query', config.query);
    params.append('shard', config.shard);
    params.append('variable', config.variable);

    return this.get('/wps/search/variable', params)
      .then(response => {
        return response.data as Axis[];
      });
  }

  execute(config: Configuration): Promise<string> {
    let preparedData: string;
    
    try {
      preparedData = config.prepareData();
    } catch (e) {
      return Promise.reject(e);
    }

    return this.postCSRF('/wps/execute/', preparedData).
      then(response => {
        return response.data;
      });
  }

  downloadScript(config: Configuration): Promise<any> {
    let preparedData: string;
    
    try {
      preparedData = config.prepareData();
    } catch (e) {
      return Promise.reject(e);
    }

    return this.postCSRF('/wps/generate/', preparedData)
      .then(response => {
        return response.data;
      });
  }
}
